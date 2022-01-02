# minimus

Minimus is an attempt to write my own Framework similar to Bottle, Flask, Pyramid, etc.

I was inspired by Richard Feynman, the famous physicist. He wrote on his blackboard, “What I cannot create I do not understand."  I wanted to understand some of the deeper aspects of WSGI and frameworks.  So why not, as per Feynman, create a framework so I can make a claim to understand these.

So in homage to my Framework heros-- Armin Ronacher and the Pallets Project (Flask and Pallets ecosystem), Ben Peterson (Paste), Ben Darnell (Tornado), and Marcell Helkamp (Bottle) --I humbly submit my framework however poorly written, but paved with good intentions.

I have succeeded at some level, but can't recommend you use it for production just yet.  I haven't completed writing tests yet.  So "caveat emptor."

Note: I decide to NOT make Minimus backward compatible to Python 2.7, it is past its end of support, so I feel justified!

Like Marcell's Bottle project, I decided to keep Minimus as a single file.  A bit of a PEP 20 violation except the idea of simplicity is the self-contained nature.  I failed to make it actually self contained, since to be really useful it includes Jinja2 as an import.  If you choose to use a non WSGIRef server like Paste, Gevent, Waitress more imports will be required, be forwarned.

Now, that I've spent some time creating Minimus.  I can say it is "simple" to me now.  I started writing a framework around Python Paste https://pypi.org/project/Paste/, I got a bit of confidence that I wasn't wasting my time!  But, got a little sad learning that the author Chris Dent was not actively developing it!  So after some mad refactoring I jump started the application object as a generic WSGI app.

Quickly, I started cloning some of the Python decorator approaches of Flask and Bottle.  If you know Bottle or Flask, you will recognize that I cloned their decorator approach and some function names and approaches to solving templating. Of course, the Pallets project Jinja2 is (in my opinion) the absolute best of class templating engine.  I decided NOT to reinvent that wheel (for now).

So someone who codes Flask or Bottle could do some minor refactoring and have their app running on Minimus.

```python
from minimus import Minimus

app = Minimus(__name__)

def index(environ):
    return "Hello World!"

app.add_route('/', index_view)

app.run()
```

Further... I did clone Flask's decorator routing.  Not too hard actually.  Also in the run line you will see a server selection-- I built in support for Paste, Waitress, Gevent, and WSGIRef servers (Bottle does this).  Minimus is also easily run as a WSGI app against the green unicorn (Gunicorn) or others like uwsgi, etc.

```python
from minimus import Minimus
app = Minimus(__name__)

@app.route('/', methods=['GET'])
def index(environ):
    return "Hello World!"
    
app.run(port=5000, host='127.0.0.1', server='paste')
```

Minimus can support "Class based views."  This is currently developing and only (so far) supports GET, POST, PUT, and DELETE methods. If you wanted a Pony, then get a Pony.

```python
from minimus import Minimus, ClassView

app = Minimums(__name__)

@app.route('/')
class MyHomePage(ClassView):
    def get(self, env):
        return "Hello World!"
    def post(self, env):
        return "POST request to Hello World"
        
app.run()
```
