import os
import sys
from petrarch2 import petrarch2
from tornado.ioloop import IOLoop
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from flask import Flask, jsonify, make_response
from flask.ext.restful import Api, Resource, reqparse

app = Flask(__name__)
api = Api(app)

cwd = os.path.abspath(os.path.dirname(__file__))

config = petrarch2.utilities._get_data('data/config/','PETR_config.ini')
petrarch2.PETRreader.parse_Config(config)
petrarch2.read_dictionaries()
#print(config)
#print(getattr(petrarch2,"VerbDict"))

@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)



class CodeAPI(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('events', type=dict)
        super(CodeAPI, self).__init__()

    def post(self):
        args = self.reqparse.parse_args()
        event_dict = args['events']

        try:
            event_dict_updated = petrarch2.do_coding(event_dict)
        except Exception as e:
            sys.stderr.write("An error occurred with PETR. {}\n".format(e))
            event_dict_updated = event_dict
        
        for key in event_dict_updated:
            event_dict_updated[key]['meta']['verbs']=[]
            for sent in event_dict_updated[key]['sents']:
                try:
                    temp_meta = event_dict_updated[key]['sents'][sent]['meta']
                    event_dict_updated[key]['sents'][sent]['meta']={'actortext':list(temp_meta['actortext'].values()),
                        'eventtext':list(temp_meta['eventtext'].values()),
                        'nouns':temp_meta['nouns'],
                        'actorroot':list(temp_meta['actorroot'].values())}
                except:
                    event_dict_updated[key]['sents'][sent]['meta']={'actortext':[[]],
                            'eventtext':[[]],
                            'nouns':[],
                            'actorroot':[[]]}

        return event_dict_updated


api.add_resource(CodeAPI, '/petrarch/code')

if __name__ == '__main__':
    #config = petrarch2.utilities._get_data('data/config/', 'PETR_config.ini')
    #print("reading config")
    #petrarch2.PETRreader.parse_Config(config)
    #print("reading dicts")
    #petrarch2.read_dictionaries()

    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(5001)
    IOLoop.instance().start()
