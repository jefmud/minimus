###########################################
#
# Minimus - a minimal web framework inspired by
#   Bottle, Flask, Pyramid, and Paste
#
#   Early ALPHA version 2021
#    by Jeff et. al.
#    MIT License
#    
#     Some code is influenced and "borrowed"
#     from Python Paste (under MIT license)
#       by Chris Dent (https://pypi.org/project/Paste/)
# 
#       and
#
#    Jinja2 best of class Templating
#     from the Pallets project
#       by Armin Ronacher (BSD License)
#     (https://palletsprojects.com/p/jinja/)
#
#    Other Python standard libraries included
#    also, waitress and gevent are excellent
#    choices for alternate WSGI servers
#    
###########################################
#from functools import wraps
import datetime
import json
import mimetypes
import os
import sys

from jinja2 import Environment, FileSystemLoader
import http.client
from http.cookies import SimpleCookie, Morsel, CookieError
import six, base64

#from paste.request import parse_formvars

# global level
_app_dir = None
_static_dir = None
_template_dir = None

# local utilities
def mimeguess(filename):
    """guess mimetype from filename, path, or url"""
    ext = '.' + filename.split('.')[-1].lower()
    return mimetypes.types_map.get(ext,'text/html')

def search_file(filename, *args):
    """look for a filename in several locations,
    return the actual filename that is found first or None
    args = list of directories to examine
    """
    fname = filename
    if filename.startswith('/'):
        fname = filename[1:]
    # possible paths ACTUAL PATH, relative path to app, or template_dir
    # might want to make this more specific to avoid name conflict
    
    paths = [filename, fname]
    for arg in args:
        paths.append(os.path.join(arg, fname))
          
    for fn in paths:
        if os.path.exists(fn):
            return fn
    return None

        
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
    
def get_file(filename, *args, **kwargs):
    """get text file or return None, searches the likely paths to find the file
    if not found, return None
    *args should contain directories to look into for the filename
    """
    real_filename = search_file(filename, *args)
    file_contents = None
    if real_filename: 
        if kwargs.get('ftype') == 'binary':
            with open(real_filename, 'rb') as fp:
                file_contents = fp.read()
        else:
            with open(real_filename) as fp:
                file_contents = fp.read()            
            
    return file_contents

def get_text_file(filename, *args, ftype='text'):
    """call get_file for a text file"""
    return get_file(filename, *args)

def get_file_size(filename, *args):
    """return the size of a filename, search likely paths"""
    real_filename = search_file(filename, *args)
    if real_filename:
        return os.path.getsize(real_filename)
    return 0

def ext_check(pathname, ext_list):
    """check if pathname has an extension in the ext_list"""
    for ext in ext_list:
        if pathname.lower().endswith(ext):
            return True
    return False

def real_path(path):
    return os.path.dirname(os.path.realpath(path))

# our framework
class Minimus:
    def __init__(self, app_file, template_directory=None, static_dir=None, quiet=False, charset='UTF-8'):
        global _app_dir, _template_dir, _static_dir # module will need this
        self.routes = None
        if template_directory is None:
            # default template directory
            template_directory = "templates"
        if static_dir is None:
            # default static directory
            static_dir = "static"
        # make sure we know the current app's directory in self and module
        self.secret_key = None
        self.cookies = {}
        self.debug = False
        self.charset = charset
        self.quiet = quiet
        self.app_dir = os.path.dirname(os.path.realpath(app_file))
        _app_dir = self.app_dir
        self.static_dir = static_dir
        _static_dir = static_dir
        self.template_dir = template_directory
        _template_dir = self.template_dir
        
        # request "hook" can be replaced by external callback
        self.not_found_html = self._not_found_html
        self.before_request = self._before_request
        self.after_request = self._after_request
        
        # place holders
        self.environ = None
        self.start_response = None

    def response_encode(self, x):
        if isinstance(x, str):
            return [x.encode(self.charset, 'ignore')]
        else:
            return [x]
        return x
        
    def _before_request(self, environ):
        """this is a hookable callback for BEFORE REQUEST"""
        pass
    
    def _after_request(self, environ):
        """this is a hookable callback for AFTER REQUEST"""
        pass
    
       
    def make_response(self, status_code:int, headers=None):
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
        # if headers was NOT set, use default.
        if headers is None:
            headers = [('Content-Type', f'text/html;charset={self.charset}')]
        
        if isinstance(headers, str):
            # if headers was given as a string
            headers = [('Content-Type', headers)]
            
        return status_str, headers    
    
    def abort(self, status_code:int, html_msg=None):
        """an abort response, well... could be anything"""
        status_str, headers = self.make_response(status_code)
        if html_msg is None:
            html_msg = f'<h1>{status_str}</h1>'
        self.start_response(status_str, headers)
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
        # save these to the object -may be needed by downstream methods
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
        response_body, status_str, headers = self.render_to_response(path_info)
        
        # after request
        self.after_request(environ)
        
        # classic WSGI return
        start_response(status_str, headers)
        return iter(response_body)

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
        (content, status_str, headers)
        """
        request_method = self.environ.get('REQUEST_METHOD')
        
        if not(self.routes):
            # IF NO ROUTES, then show server logo and exit
            response_body = "<pre>" + self.logo() + "</pre>"
            status_str, headers = self.make_response(200)
            headers.append(('Content-Length', str(len(response_body))))
            return self.response_encode(response_body), status_str, headers
            
        # handle static files
        if self.static_dir in path_info:
            # search the usual locations for our file, return if exists
            local_fname = search_file(path_info, self.app_dir, self.static_dir, self.template_dir)
            
            # interpret response by filename extension
            if local_fname:
                # handle css and javascript status, headers
                if path_info.endswith('.css'):
                    response_body = get_text_file(path_info)                    
                    status_str, headers = self.make_response(200, 'text/css')
                elif path_info.endswith('.js'):
                    response_body = get_text_file(path_info)
                    status_str, headers = self.make_response(200, 'text/javascript')
                elif ext_check(path_info, ['jpg', 'jpeg', 'gif', 'png', 'ico']):
                    # image rendering short circuits below to return
                    response_body = get_file(path_info, ftype='binary')
                    status_str = '200 OK'
                    # construct headers to contain expected image type
                    mimetype = mimeguess(path_info)
                    headers = [ ('Content-Type', mimetype), ('Cache-Control', 'public, max-age=43200') ]
                    headers.append(('Content-Length', str(len(response_body))))
                    # returning image here 3-tuple
                    return [response_body], status_str, headers
                else:
                    # default html/text
                    response_body = get_text_file(path_info)
                    status_str, headers = self.make_response(200)
            else:
                # path_info file not found, respond 404
                status_str, headers = self.make_response(404)
                response_body = self.not_found_html()
                
            ### RETURN STATIC CONTENT or NOT FOUND ###
            # finally add the content length to the headers
            headers.append(('Content-Length', str(len(response_body))))
            # return the 3-tuple
            return self.response_encode(response_body), status_str, headers
        
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
                            response_body = handler_response[0]
                            status_str = handler_response[1]
                            headers = handler_response[2]
                        else:
                            # return of content and status_code integer
                            status_str, headers = self.make_response(int(handler_response[1]))
                            response_body = handler_response[0]
                    else:
                        # simple status 200 is just a string!
                        if isinstance(handler_response, str): 
                            status_str, headers = self.make_response(200)
                            response_body = handler_response
                        else:
                            # if not a string, programmer screwed up return a 400 Bad Response
                            status_str, headers = self.make_response(400)
                            response_body = f'<h1>{path_info} produced incompatible response.</h1>\n<p>None type returned</p>'

                else:
                    # return a 405 error, method not allowed.
                    status_str, headers = self.make_response(405)
                    response_body = '<h1>405 Method not allowed</h1>'
                    
                # finally return our response to wsgi server
                
                headers.append(('Content-Length', str(len(response_body))))              
                return self.response_encode(response_body), status_str, headers

        # no matching route found, respond 404
        status_str, headers = self.make_response(404)
        response_body = self.not_found_html()
        headers.append(('Content-Length', str(len(response_body))))        
        return self.response_encode(response_body), status_str, headers
    
    
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
            
    def jsonify(self, datadict):
        # encode and return JSON, may have to get BSON for some encodings
        response_body = json.dumps(datadict)
        headers = [('Content-Type',f'application/json;charset={self.charset}')]
        headers.append(('Content-Length', str(len(response_body))))
        return response_body, '200 OK', headers
    
    def get_cookies(self, environ):
        """
        Gets a cookie object (which is a dictionary-like object) from the
        request environment; caches this value in case get_cookies is
        called again for the same request.
        """
        header = environ.get('HTTP_COOKIE', '')
        if 'minimus.cookies' in environ:
            cookies, check_header = environ['minimus.cookies']
            if check_header == header:
                return cookies
        cookies = SimpleCookie()
        try:
            cookies.load(header)
        except CookieError:
            pass
        environ['minimus.cookies'] = (cookies, header)
        return cookies
    
    def set_cookie_header(self, name, value, secret=None, days=365):
        dt = datetime.datetime.now() + datetime.timedelta(days=days)
        fdt = dt.strftime('%a, %d %b %Y %H:%M:%S GMT')
        secs = days * 86400
        if secret:
            value = encode(secret, value)
        return ('Set-Cookie', '{}={}; Expires={}; Max-Age={}; Path=/'.format(name, value, fdt, secs))
    
    def get_cookie(self, name, secret=None):
        """need to encrypt the cookies, we should get there soon"""
        cookies = self.get_cookies(self.environ)
        morsel = cookies.get(name)
        if secret:
            value = decode(secret, morsel.value)
        else:
            value = morsel.value
        return value
    
def send_from_directory(filename, *args, **kwargs):
    """sends a file from directory(filename, args=list of directories to try, kwargs=keyword arguments)
    possible keyword arguments
    mimetype='image/png'
    ftype='binary'
    """
    response_body = get_file(filename, *args, **kwargs)
    if response_body:
        # set the mimetype
        if 'mimetype' in kwargs:
            mimetype = kwargs['mimetype']
        else:
            mimetype = mimeguess(filename)
            
        status_str = '200 OK'
        headers = [('Content-Type', mimetype), ('Cache-Control', 'public, max-age=43200')]
        if kwargs.get('as_attachment'):
            headers.append(('Content-Disposition', f'attachment; filename={filename}'))
            
    else:
        response_body = f'named resource not found: <b>{filename}</b>'
        status_str = '404 ERROR'
        headers = [('Content-Type','text/html')]
        
    return response_body, status_str, headers
                   

def render_template(filename, **kwargs):
    """flexible jinja2 rendering of filename and kwargs"""
    template_dir = ''
    static_dir =''
    if 'template_dir' in kwargs:
        template_dir = kwargs.get('template_dir')
    if 'static_dir' in kwargs:
        static_dir = kwargs.get('static_dir')
    if _template_dir:
        # Minimus apps go this way, they will know the default template dir
        file_content = get_text_file(filename, _template_dir, template_dir)
        template_dir = _template_dir
    else:
        # non-Minimus users go this way
        #real_file = search_file(filename, *args)
        #template_dir = os.path.dirname(real_file)
        file_content = get_text_file(filename, template_dir, static_dir)
        
    if file_content:
        template = Environment(loader=FileSystemLoader([template_dir], followlinks=True)).from_string(file_content)
        #template = jinja2.Template(file_content)
        return template.render(**kwargs)
    return "ERROR: render_template - Failed to find {}".format(filename)

def render_html_file(filename, *args):
    """flexible straight HTML rendering of filename"""
    if _template_dir:
        # Minimus apps use this route
        file_content = get_text_file(filename, _template_dir, *args)
    else:
        # if a different call is made
        file_content = get_text_file(filename, *args)
    
    if file_content:
        return file_content
    else:
        return 'ERROR: render_html_file - Failed to find {}'.format(filename)

# Python 3 standard
from collections.abc import MutableMapping
class MultiDict(MutableMapping):

    """
    An ordered dictionary that can have multiple values for each key.
    Adds the methods getall, getone, mixed, and add to the normal
    dictionary interface.
    
    Class Attribution: BENJAMIN PETERSON (Python Paste) Thanks Ben!
    Only minor modifications were required.
    (https://github.com/cdent/paste/blob/master/paste/util/multidict.py)
    """

    def __init__(self, *args, **kw):
        if len(args) > 1:
            raise TypeError(
                "MultiDict can only be called with one positional argument")
        if args:
            if hasattr(args[0], 'iteritems'):
                items = args[0].iteritems()
            elif hasattr(args[0], 'items'):
                items = args[0].items()
            else:
                items = args[0]
            self._items = list(items)
        else:
            self._items = []
        self._items.extend(six.iteritems(kw))

    def __getitem__(self, key):
        for k, v in self._items:
            if k == key:
                return v
        raise KeyError(repr(key))

    def __setitem__(self, key, value):
        try:
            del self[key]
        except KeyError:
            pass
        self._items.append((key, value))

    def add(self, key, value):
        """
        Add the key and value, not overwriting any previous value.
        """
        self._items.append((key, value))

    def getall(self, key):
        """
        Return a list of all values matching the key (may be an empty list)
        """
        result = []
        for k, v in self._items:
            if type(key) == type(k) and key == k:
                result.append(v)
        return result

    def getone(self, key):
        """
        Get one value matching the key, raising a KeyError if multiple
        values were found.
        """
        v = self.getall(key)
        if not v:
            raise KeyError('Key not found: %r' % key)
        if len(v) > 1:
            raise KeyError('Multiple values match %r: %r' % (key, v))
        return v[0]

    def mixed(self):
        """
        Returns a dictionary where the values are either single
        values, or a list of values when a key/value appears more than
        once in this dictionary.  This is similar to the kind of
        dictionary often used to represent the variables in a web
        request.
        """
        result = {}
        multi = {}
        for key, value in self._items:
            if key in result:
                # We do this to not clobber any lists that are
                # *actual* values in this dictionary:
                if key in multi:
                    result[key].append(value)
                else:
                    result[key] = [result[key], value]
                    multi[key] = None
            else:
                result[key] = value
        return result

    def dict_of_lists(self):
        """
        Returns a dictionary where each key is associated with a
        list of values.
        """
        result = {}
        for key, value in self._items:
            if key in result:
                result[key].append(value)
            else:
                result[key] = [value]
        return result

    def __delitem__(self, key):
        items = self._items
        found = False
        for i in range(len(items)-1, -1, -1):
            if type(items[i][0]) == type(key) and items[i][0] == key:
                del items[i]
                found = True
        if not found:
            raise KeyError(repr(key))

    def __contains__(self, key):
        for k, v in self._items:
            if type(k) == type(key) and k == key:
                return True
        return False

    has_key = __contains__

    def clear(self):
        self._items = []

    def copy(self):
        return MultiDict(self)

    def setdefault(self, key, default=None):
        for k, v in self._items:
            if key == k:
                return v
        self._items.append((key, default))
        return default

    def pop(self, key, *args):
        if len(args) > 1:
            raise TypeError("pop expected at most 2 arguments, got "
                              + repr(1 + len(args)))
        for i in range(len(self._items)):
            if type(self._items[i][0]) == type(key) and self._items[i][0] == key:
                v = self._items[i][1]
                del self._items[i]
                return v
        if args:
            return args[0]
        else:
            raise KeyError(repr(key))

    def popitem(self):
        return self._items.pop()

    def update(self, other=None, **kwargs):
        if other is None:
            pass
        elif hasattr(other, 'items'):
            self._items.extend(other.items())
        elif hasattr(other, 'keys'):
            for k in other.keys():
                self._items.append((k, other[k]))
        else:
            for k, v in other:
                self._items.append((k, v))
        if kwargs:
            self.update(kwargs)

    def __repr__(self):
        items = ', '.join(['(%r, %r)' % v for v in self._items])
        return '%s([%s])' % (self.__class__.__name__, items)

    def __len__(self):
        return len(self._items)

    ##
    ## All the iteration:
    ##

    def keys(self):
        return [k for k, v in self._items]

    def iterkeys(self):
        for k, v in self._items:
            yield k

    __iter__ = iterkeys

    def items(self):
        return self._items[:]

    def iteritems(self):
        return iter(self._items)

    def values(self):
        return [v for k, v in self._items]

    def itervalues(self):
        for k, v in self._items:
            yield v

from urllib.parse import parse_qsl            
def parse_querystring(environ):
    """
    Parses a query string into a list like ``[(name, value)]``.
    Caches this value in case parse_querystring is called again
    for the same request.
    You can pass the result to ``dict()``, but be aware that keys that
    appear multiple times will be lost (only the last value will be
    preserved).
    
    Function Attribution: BENJAMIN PETERSON (Python Paste)
    (https://github.com/cdent/paste/blob/master/paste/util/multidict.py)
    """
    source = environ.get('QUERY_STRING', '')
    if not source:
        return []
    if 'paste.parsed_querystring' in environ:
        parsed, check_source = environ['paste.parsed_querystring']
        if check_source == source:
            return parsed
    parsed = parse_qsl(source, keep_blank_values=True,
                       strict_parsing=False)
    environ['paste.parsed_querystring'] = (parsed, source)
    return parsed

import six
import cgi
def parse_formvars(environ, include_get_vars=True, encoding=None, errors=None):
    """Parses the request, returning a MultiDict of form variables.
    If ``include_get_vars`` is true then GET (query string) variables
    will also be folded into the MultiDict.
    All values should be strings, except for file uploads which are
    left as ``FieldStorage`` instances.
    If the request was not a normal form request (e.g., a POST with an
    XML body) then ``environ['wsgi.input']`` won't be read.
    
    Function Attribution: BENJAMIN PETERSON (Python Paste)
    (https://github.com/cdent/paste/blob/master/paste/util/multidict.py)
    """
    source = environ['wsgi.input']
    if 'paste.parsed_formvars' in environ:
        parsed, check_source = environ['paste.parsed_formvars']
        if check_source == source:
            if include_get_vars:
                parsed.update(parse_querystring(environ))
            return parsed
    # @@: Shouldn't bother FieldStorage parsing during GET/HEAD and
    # fake_out_cgi requests
    formvars = MultiDict()
    ct = environ.get('CONTENT_TYPE', '').partition(';')[0].lower()
    use_cgi = ct in ('', 'application/x-www-form-urlencoded',
                                'multipart/form-data')
    # FieldStorage assumes a default CONTENT_LENGTH of -1, but a
    # default of 0 is better:
    if not environ.get('CONTENT_LENGTH'):
        environ['CONTENT_LENGTH'] = '0'
    if use_cgi:
        # Prevent FieldStorage from parsing QUERY_STRING during GET/HEAD
        # requests
        old_query_string = environ.get('QUERY_STRING','')
        environ['QUERY_STRING'] = ''
        inp = environ['wsgi.input']
        kwparms = {}
        if six.PY3:
            if encoding:
                kwparms['encoding'] = encoding
            if errors:
                kwparms['errors'] = errors
        fs = cgi.FieldStorage(fp=inp,
                              environ=environ,
                              keep_blank_values=True,
                              **kwparms)
        environ['QUERY_STRING'] = old_query_string
        if isinstance(fs.value, list):
            for name in fs.keys():
                values = fs[name]
                if not isinstance(values, list):
                    values = [values]
                for value in values:
                    if not value.filename:
                        value = value.value
                    formvars.add(name, value)
    environ['paste.parsed_formvars'] = (formvars, source)
    if include_get_vars:
        formvars.update(parse_querystring(environ))
    return formvars



def encode(key, string):
    encoded_chars = []
    for i in range(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(ord(string[i]) + ord(key_c) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = ''.join(encoded_chars)
    encoded_string = encoded_string.encode('latin') if six.PY3 else encoded_string
    return base64.urlsafe_b64encode(encoded_string).rstrip(b'=')

def decode(key, string):
    string = b"b's9LHug'"
    string = base64.urlsafe_b64decode(string + b'===')
    #string = base64.urlsafe_b64decode(string)
    string = string.decode('latin') if six.PY3 else string
    encoded_chars = []
    for i in range(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr((ord(string[i]) - ord(key_c) + 256) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = ''.join(encoded_chars)
    return encoded_string

def encode_tests():
    print("* encode_test")
    key = 'IamASecret'
    string = 'Santa Claus is coming to town!'
    encval = encode(key, string)
    decval = decode(key, encval)
    assert(string!=encval)
    assert(string==decval)
    assert(route_encode('/edit') == '/edit')
    assert(route_encode('/edit/<page>', page=1) == '/edit/1')
    assert(route_encode('/page/<page>/delete', page=1) == '/page/1/delete')
    assert(route_encode('/page/<page>/<obj>', page=1, obj=2) == '/page/1/2')
    print("  tests pass")

def file_tests():
    print("* file tests")
    app_dir = real_path(__name__)
    templates_dir = os.path.join(app_dir, 'templates')
    content = get_file('page.html', app_dir, templates_dir)
    assert(content)
    content = get_file('page.html', 'templates')
    assert(content)
    content = get_file('img/cupcake.png','static', ftype='binary')
    assert(content)
    print("  tests pass")

def template_tests():
    print("* template tests")
    # look for a template where template_dir is a parameter
    content = render_template('ribbit/index.html', template_dir='templates', static_dir='static')
    assert(not('404' in content))    
    global _template_dir
    # a typical Minimus app will have the relative path 'templates'
    _template_dir = 'templates'
    content = render_template('page.html')
    assert(not('404' in content)) 
    
    print("    tests pass")
    
if __name__ == '__main__':
    # test route_encode
    encode_tests()
    file_tests()
    template_tests()