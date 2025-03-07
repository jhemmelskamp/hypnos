import os
import json
import requests
from tornado.ioloop import IOLoop
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from flask import Flask, jsonify, make_response
from flask_restful import Api, Resource, reqparse
from logging import getLogger

app = Flask(__name__)
api = Api(app)

cwd = os.path.abspath(os.path.dirname(__file__))

logger = getLogger()

@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


def format_parsed_str(parsed_str):
    # This helper function strips off the outer ROOT tags
    if parsed_str.strip().startswith("(ROOT") and parsed_str.strip().endswith(")"):
        parsed_str = parsed_str.strip()[5:-1].strip()
    elif parsed_str.strip()[1:].strip().startswith("("):
        parsed_str = parsed_str.strip()[1:-1]
    parsed = parsed_str.split('\n')
    parsed = [line.strip() + ' ' for line in [line1.strip() for line1 in parsed if line1] if line]
    parsed = [line.replace(')', ' ) ').upper() for line in parsed]
    treestr = ''.join(parsed)
    return treestr


class ExtractAPI(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        # In Python 2.7, use type=unicode for JSON fields
        self.reqparse.add_argument('text', type=unicode, location='json', required=True,
                                   help="Text cannot be blank!")
        self.reqparse.add_argument('id', type=unicode, location='json', required=True,
                                   help="ID cannot be blank!")
        self.reqparse.add_argument('date', type=unicode, location='json', required=True,
                                   help="Date cannot be blank!")
        super(ExtractAPI, self).__init__()

    def get(self):
        args = self.reqparse.parse_args()
        text = args['text']
        # If necessary, convert Unicode to a byte string:
        # text = text.encode('utf-8')
        storyid = args['id']
        date = args['date']

        out = send_to_ccnlp(text)
        if out is None:
            return {"error": "Failed to process CoreNLP request"}, 500

        event_dict = process_corenlp(out, date, storyid)

        event_updated = send_to_petr(event_dict)
        if event_updated is None:
            return {"error": "Failed to update PETR service"}, 500

        return event_updated


def send_to_ccnlp(text):
    """
    Sends the text to the CoreNLP server. The URL is adjusted to request JSON output.
    If needed, you can add additional properties (e.g., annotators) to the JSON payload.
    """
    ccnlp_url = 'http://ccnlp:5000/process?outputFormat=json&annotators=tokenize,ssplit,pos,lemma,ner,parse'
    try:
        headers = {'Content-Type': 'application/json'}
        core_data = text
        response = requests.post(ccnlp_url, data=core_data, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
    except requests.exceptions.RequestException as e:
        print("Error sending request: {}".format(e))
        return None

    return response.json()


def send_to_petr(event_dict):
    """
    Sends the event dictionary to the PETR service.
    """
    headers = {'Content-Type': 'application/json'}
    events_data = json.dumps({'events': event_dict})
    petr_url = 'http://petrarch:5001/petrarch/code'
    try:
        events_r = requests.post(petr_url, data=events_data, headers=headers)
        events_r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Error sending to PETR: {}".format(e))
        return None
    event_updated = events_r.json()
    return event_updated


def process_corenlp(output, date, STORYID):
    """
    Processes the output from the CoreNLP server.
    The new Stanford CoreNLP version returns tokens as dictionaries.
    """
    event_dict = {STORYID: {'sents': {}, 'meta': {'date': date}}}
    
    for i, sent in enumerate(output.get('sentences', [])):
        sent_id = str(i)
        event_dict[STORYID]['sents'][sent_id] = {}
        
        tokens = sent.get('tokens', [])
        if tokens and isinstance(tokens[0], dict):
            # Extract the 'word' field from each token dictionary.
            token_words = [token.get('word', '') for token in tokens]
        else:
            token_words = tokens  # fallback if tokens are plain strings

        event_dict[STORYID]['sents'][sent_id]['content'] = ' '.join(token_words)
        
        parse_str = sent.get('parse')
        if parse_str:
            event_dict[STORYID]['sents'][sent_id]['parsed'] = format_parsed_str(parse_str)
        else:
            event_dict[STORYID]['sents'][sent_id]['parsed'] = None

    return event_dict


def process_results(event_dict):
    """
    This helper function ensures that each sentence in the event dictionary
    has 'issues' and 'events' keys.
    """
    for s_id in event_dict:
        sents = event_dict[s_id]['sents']
        for sent in sents:
            if 'issues' not in sents[sent]:
                sents[sent]['issues'] = []
            if 'events' not in sents[sent]:
                sents[sent]['events'] = []
    return event_dict


# Register the resource with its endpoint.
api.add_resource(ExtractAPI, '/hypnos/extract')

if __name__ == '__main__':
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(5002)
    IOLoop.instance().start()
