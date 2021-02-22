# minimus

Minimus is an attempt to write my own Framework similar to Bottle, Flask, Pyramid, etc.

I was inspired by Richard Feynman, the famous physicist. He wrote on his blackboard, “What I cannot create I do not understand."  I wanted to understand some of the deeper aspects of WSGI and frameworks.  So why not, as per Feynman, create a framework so I can make a claim to understand these.

I have succeeded at some level, but can't recommend you use it just yet.

Now, that I've spent some time creating one.  I never knew that these were way more simple than I had expected and that found it works pretty well.  I started writing a framework around Python Paste https://pypi.org/project/Paste/, I got a bit of confidence that I wasn't wasting my time!  But, got a little sad learning that the author Chris Dent was not actively developing it!  So after some mad refactoring I jump started the application object as a generic WSGI app.

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
