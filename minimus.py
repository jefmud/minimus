###########################################
# Minimus - a minimal web framework inspired by
#   Bottle, Flask, and Pyramid
#
#   Early ALPHA version 2021
#    by Jeff et. al.
#    MIT License
#    depends upon import of Python Paste
#       by Chris Dent (https://pypi.org/project/Paste/)
#     MIT License
#       and
#    Jinja2 Templating from the Pallets project
#     by Armin Ronacher (BSD License)
#     (https://palletsprojects.com/p/jinja/)
#    
###########################################
from functools import wraps
import os

from jinja2 import Environment, FileSystemLoader
import http.client

from paste.request import parse_formvars
from paste.httpexceptions import HTTPError

# global level
app_dir = None
static_dir = None
template_dir = None

# local utilities
def search_file(filename):
    """look for a filename in several locations,
    return the actual filename that is found first or None
    """
    fname = filename
    if filename.startswith('/'):
        fname = filename[1:]
    # possible paths ACTUAL PATH, relative path to app, or template_dir
    # might want to make this more specific to avoid name conflict
    paths = [
        filename,
        fname,
        os.path.join(app_dir, fname),
        os.path.join(app_dir, template_dir, fname)
    ]
    for fn in paths:
        if os.path.exists(fn):
            return fn
    return None



module_start_response = None
module_environ = None
        
def route_match(route, path):
    """will return simple path and dictionary (keyword arguments)
    route = framework route syntax route
    path = environment PATH_INFO
    route is of the form /thispage
    or a route with a variable /thispage/<var>
    or the SPECIAL path /something/<mypath:path> which captures
    an entire path in that position
    """
    # explode the route and path parts
    rparts = route.split('/')
    pparts = path.split('/')
    # return keyword arguments as kwargs
    kwargs = {}
    if not(':path' in route) and (len(rparts) != len(pparts)):
        return False, kwargs
    for idx, rp in enumerate(rparts):
        # handle variable in the path
        if '<' in rp:
            # handle variable
            b1 = rp.find('<')
            b2 = rp.find('>')
            if b2 <= b1:
                # malformed, fail
                return False, kwargs
            varname = rp[b1+1:b2]
            if ':path' in varname:
                varname = varname.replace(':path','')
                i = idx
                pathval = ""
                while i < len(pparts):
                    pathval += '/' + pparts[i]
                    i += 1
                #todo, escape the pathval
                kwargs[varname] = pathval
                return True, kwargs
            else:
                kwargs[varname] = pparts[idx]
        elif rp != pparts[idx]:
            return False, kwargs
    # all done, the path matched and here are the keyword args (if any)
    return True, kwargs

def route_encode(route, **kwargs):
    """given a route and matching kwargs, return a URL
    e.g. route = '/hello/<name>' kwargs={"name":"George"}
    will produce /hello/George
    """
    rparts = route.split('/')
    nparts = []
    for rp in rparts:
        if '<' in rp:
            # handle variable
            b1 = rp.find('<')
            b2 = rp.find('>')
            if b2 <= b1:
                # malformed, fail
                return False, kwargs
            varname = rp[b1+1:b2]
            varval = kwargs.get(varname, None)
            if varval:
                nparts.append(str(varval))
            else:
                raise ValueError(f"route_encode() - {varname} not in keyword args")
        else:
            nparts.append(rp)
    url = '/'.join(nparts)
    return url
            
        
def route_decode(route):
    """maybe I don't need this since I use route_match above"""
    kwargs={}
    return route, kwargs
    
def get_file(filename, ftype='text'):
    """get text file or return None, searches the likely paths to find the file
    if not found, return None
    """
    # check if we have absolute path correct or if it belongs to app_path hierarchy
    real_filename = search_file(filename)
    file_contents = None
    if real_filename:
        if ftype == 'text':
            with open(real_filename) as fp:
                file_contents = fp.read()
        if ftype == 'binary':
            with open(real_filename, 'rb') as fp:
                file_contents = fp.read()            
    return file_contents

def get_text_file(filename):
    """call get_file for a text file"""
    return get_file(filename)

def get_file_size(filename):
    """return the size of a filename, search likely paths"""
    real_filename = search_file(filename)
    if real_filename:
        return os.path.getsize(real_filename)
    return 0

def ext_check(pathname, ext_list):
    """check if pathname has an extension in the ext_list"""
    for ext in ext_list:
        if pathname.lower().endswith(ext):
            return True
    return False

# our framework
class Minimus:
    def __init__(self, app_file, template_directory=None, static_dir=None, quiet=False, charset='UTF-8'):
        global app_dir, template_dir # module will need this
        self.routes = None
        if template_directory is None:
            # default template directory
            template_directory = "templates"
        if static_dir is None:
            # default static directory
            static_dir = "static"
        # make sure we know the current app's directory in self and module
        self.debug = False
        self.charset = charset
        self.quiet = quiet
        self.app_dir = os.path.dirname(os.path.realpath(app_file))
        app_dir = self.app_dir
        self.static_dir = static_dir
        self.template_dir = template_directory
        template_dir = self.template_dir
        
        # request "hook" can be replaced by external callback
        self.not_found_html = self._not_found_html
        self.before_request = self._before_request
        self.after_request = self._after_request
        
        # place holders
        self.environ = None
        self.start_response = None

    def bin_encode(self, x):
        if isinstance(x, str):
            return [x.encode(self.charset, 'ignore')]
        return x
        
    def _before_request(self, environ):
        """this is a hookable callback for BEFORE REQUEST"""
        pass
    
    def _after_request(self, environ):
        """this is a hookable callback for AFTER REQUEST"""
        pass
    
       
    def make_response(self, status_code:int, ctype=None):
        """
        make status string and  content-type WSGI compliant
        returns the status string and content-type list/tuple
        
        Can be used in three ways examples below:
        make_response(200) ==> 200 OK, [('Content-Type', 'text/html')]
        make_response(200, 'text/css') ==> 200 OK [('Content-Type', 'text/css')]
        make_response(503, [('Content-Type','text/html')])
        """
        # build the status string, using the standard helper
        rstr = http.client.responses.get(status_code, 'UNKNOWN')
        status_str = f"{status_code} {rstr}"
        # if ctype was NOT set, use default.
        if ctype is None:
            ctype = [('Content-Type', f'text/html;charset={self.charset}')]
        
        if isinstance(ctype, str):
            # if ctype was given as a string
            ctype = [('Content-Type', ctype)]
            
        return status_str, ctype    
    
    def abort(self, status_code:int, html_msg=None):
        """an abort response, well... could be anything"""
        status_str, ctype = self.make_response(status_code)
        if html_msg is None:
            html_msg = f'<h1>{status_str}</h1>'
        self.start_response(status_str, ctype)
        return [str.encode(html_msg)]
    
    def wsgi(self, environ, start_response):
        """The main WSGI application.  Supports WSGI standard can be exposed to
        work with external WSGI servers.
        
        In the __main__ you could do this below.  Then Gunicorn can hook onto
        it  $ gunicorn app.wsgi -b 127.0.0.1:8000
        
        # app.py
        app = Minimus(__name__)
        wsgi = app.wsgi
        """
        # save these locally
        self.start_response = start_response
        self.environ = environ
        
        # debug shows environment on server console
        if self.debug:
            print("-"*50)
            print(environ)

        # before request -- can be "hooked" at application level
        self.before_request(environ)

        # route dispatcher
        path_info = environ.get('PATH_INFO')
        content, status_str, ctype = self.render_to_response(path_info)
        
        # after request
        self.after_request(environ)
        
        start_response(status_str, ctype)
        return iter(content)

    def add_route(self, route, handler, methods=None, name=None):
        """simple route addition to Mimimus application object
        :param route: - supports simple static routes (must begin with a slash) as well as named variables.
        It also supports a special PATH catchment variable e.g. "/blog/<mypath:path>"
        handler - callback function that handles the route.  By default the callback's first
        parameter is an environment variable.  The callback can also have OTHER paramerters that
        match the variables.
        :param methods: (list) - HTTP Methods supported, by default it supports ["GET","POST"]
        :param name: - the name of the route used by app.url_for(name) routing
        """
        if methods is None:
            methods = ['GET','POST']
        if not isinstance(methods, list):
            raise ValueError('Minimus add_route route={} methods must be a list type')
        if self.routes is None:
            self.routes = []
        # avoid duplication
        for r in self.routes:
            if r == route:
                return
        # finally, add route
        self.routes.append((route,handler,methods,name))

    def _not_found_html(self):
        """just return some text for the 404.  This can be replaced with app level function
        # app.py
        app = Minimus(__name__)
        def my404():
            return "My 404 message!"
        app.not_found_html=my404
        """
        return '<h1>404 Not Found</h1>'
    
    def run(self, host='127.0.0.1', port=5000, server='wsgiref', debug=False):
        """run() starts a "internal" server at host/port with server
        :param host: default=127.0.0.1, but can be '0.0.0.0' for serve to all
        :param port: default=5000
        :param server: default='wsgiref' other servers supported 'paste','waitress','gevent'
        """
        print(self.logo())

        self.debug = debug
        self.host = host
        self.port = port
        self.server = server

        if server == 'paste':
            """Start the server with the paste server"""
            from paste import httpserver
            from paste.translogger import TransLogger
            handler = TransLogger(self.wsgi, setup_console_handler=(not self.quiet))
            print("Starting Paste Server")
            httpserver.serve(handler, host=host, port=port)

        if server == 'wsgiref':
            from wsgiref.simple_server import make_server
            with make_server(host, port, self.wsgi) as httpd:
                print("WSGIREF Serving on {}:{}".format(host, port))
                httpd.serve_forever()

        if server == 'gevent':
            from gevent import pywsgi
            address = (host, port)
            print("Gevent serving on {}:{}".format(host, port))
            httpd = pywsgi.WSGIServer(address, self.wsgi)
            httpd.serve_forever()

        if server == 'waitress':
            from waitress import serve
            print("Waitress serving on {}:{}".format(host, port))
            serve(self.wsgi, host=host, port=port, _quiet=self.quiet)


    def route_by_name(self, name):
        """given a route_name, return the route"""
        for route, callback, methods, _name in self.routes:
            if name == _name:
                return route
        return None

    def url_for(self, name, **kwargs):
        """kwargs are NOT handled yet
        suppose a route /edit_page/<idx> ==> edit_page(env, idx), name="edit"
        url_for("edit", 22) ==> /edit_page/22
        """
        route = self.route_by_name(name)
        url = route_encode(route, **kwargs)
        return url
    
    def render_to_response(self, path_info):
        """render a path and its response to a three tuple
        (content, status_str, content-type)
        """
        request_method = self.environ.get('REQUEST_METHOD')
        
        if not(self.routes):
            # IF NO ROUTES, then show server logo and exit
            status_str, ctype = self.make_response(200)
            ### RETURN 200 Logo (DEFAULT NO ROUTES) ###
            content = "<pre>" + self.logo() + "</pre>"
            return self.bin_encode(content), status_str, ctype
            
        # handle static files
        if self.static_dir in path_info:
            content = get_file(path_info, ftype='binary')
            
            # interpret response by filename extension
            if content:
                # handle css and javascript status, ctype
                if path_info.endswith('.css'):
                    content = get_text_file(path_info)                    
                    status_str, ctype = self.make_response(200, 'text/css')
                elif path_info.endswith('.js'):
                    content = get_text_file(path_info)
                    status_str, ctype = self.make_response(200, 'text/javascript')
                elif ext_check(path_info, ['jpg', 'jpeg', 'gif', 'png']):
                    # image rendering short circuits
                    content = get_file(path_info, ftype='binary')
                    status_str = '200 OK'
                    ext = path_info[-3:]
                    ctype = [ ('Content-Type', f'image/{ext}'), ('Content-length', str(len(content))) ]
                    return [content], status_str, ctype
                else:
                    # default
                    content = get_text_file(path_info)
                    status_str, ctype = self.make_response(200)
            else:
                # path_info file not found, respond 404
                status_str, ctype = self.make_response(404)
                content = self.not_found_html()
                
            ### RETURN STATIC CONTENT or NOT FOUND ###
            return self.bin_encode(content), status_str, ctype
        
        ### Handle routes    
        for route, handler, methods, _ in self.routes:
            # check for a route match and get any keyword arguments
            match, kwargs = route_match(route, path_info)
            # the path matches the route
            if match:
                # make sure METHODS are correct for the route
                if request_method in methods:
                    # get the handler/callback response
                    handler_response = handler(self.environ, **kwargs)
                    
                    if isinstance(handler_response, tuple): 
                        if len(handler_response) == 3:
                            # fully formed response is a 3-tuple
                            content = handler_response[0]
                            status_str = handler_response[1]
                            ctype = handler_response[2]
                        else:
                            # return of content and status_code integer
                            status_str, ctype = self.make_response(int(handler_response[1]))
                            content = handler_response[0]
                    else:
                        # simple status 200 is just a string!
                        if isinstance(handler_response, str): 
                            status_str, ctype = self.make_response(200)
                            content = handler_response
                        else:
                            # if not a string, programmer screwed up return a 400 Bad Response
                            status_str, ctype = self.make_response(400)
                            content = f'<h1>{path_info} produced incompatible response.</h1>\n<p>None type returned</p>'

                else:
                    # return a 405 error, method not allowed.
                    status_str, ctype = self.make_response(405)
                    content = '<h1>405 Method not allowed</h1>'
                    
                # finally return our response to wsgi server
                return self.bin_encode(content), status_str, ctype

        # no matching route found, respond 404
        status_str, ctype = self.make_response(404)
        content = self.not_found_html()
        return self.bin_encode(content), status_str, ctype
    
    
    def redirect(self, path_info):
        return self.render_to_response(path_info)

    def logo(self):
        """logo() - renders a simple text logo for the server"""
        logo_text=\
r"""
  __  __ _       _
 |  \/  (_)     (_)
 | \  / |_ _ __  _ _ __ ___  _   _ ___
 | |\/| | | '_ \| | '_ ` _ \| | | / __|
 | |  | | | | | | | | | | | | |_| \__ \
 |_|  |_|_|_| |_|_|_| |_| |_|\__,_|___/
------------------------------------------
 A Minimal Python Framework
 (C) 2021 Jeff et. al.
 -----------------------------------------
"""
        return logo_text
    
    def route(self, url, methods=None, name=None):
        """route decorator ala Flask and Bottle
        url is mandatory and follows route rules and var naming
        @app.route(/hello, methods=['GET'], name="hello")
        @app.route('/greet/<name>', name='greet_name')
        """
        def inner_decorator(f):
            #print(f.__name__, url, methods, name)
            self.add_route(url, f, methods=methods, name=name)
            return f
        return inner_decorator
            
        
def render_template(filename, **kwargs):
    """flexible jinja2 rendering of filename and kwargs"""
    file_content = get_text_file(filename)
    if file_content:
        template = Environment(loader=FileSystemLoader(template_dir)).from_string(file_content)
        #template = jinja2.Template(file_content)
        return template.render(**kwargs)
    return "ERROR: render_template - Failed to find {}".format(filename)

def render_html_file(filename):
    """flexible straight HTML rendering of filename"""
    file_content = get_text_file(filename)
    if file_content:
        return file_content
    else:
        return 'ERROR: render_html_file - Failed to find {}'.format(filename)


if __name__ == '__main__':
    # test route_encode
    assert(route_encode('/edit') == '/edit')
    assert(route_encode('/edit/<page>', page=1) == '/edit/1')
    assert(route_encode('/page/<page>/delete', page=1) == '/page/1/delete')
    assert(route_encode('/page/<page>/<obj>', page=1, obj=2) == '/page/1/2')
    print("tests pass")