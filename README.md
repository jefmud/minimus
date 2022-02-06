# minimus

Minimus is an attempt to write my own Framework similar to Bottle, Flask, Pyramid, etc.

I was inspired by **Richard Feynman**, the famous physicist. He wrote on his blackboard, **“What I cannot create I do not understand."**  I wanted to understand some of the deeper aspects of WSGI and frameworks.  So why not, as per Feynman, create a framework so I can make a claim to understand these.

*I set forth on a rainy Saturday and a few cups of coffee to have a bit of fun with writing this...*

So in homage to my Framework heros-- **Armin Ronacher and the Pallets Project** (Flask, Werkzeug, and Pallets ecosystem), **Chris Dent and Ben Peterson** (Paste), **Ben Darnell** (Tornado), and especially **Marcell Helkamp** (Bottle) --I humbly submit my framework however poorly written, but paved with good intentions.

I have succeeded at some level, but can't recommend you use it for production just yet.  I haven't completed writing tests yet.  So "caveat emptor."

Note: I decide to NOT make Minimus backward compatible to Python 2.7, it is past its end of support, so I feel justified!

Like Marcell's Bottle project, I decided to keep Minimus as a single file.  A bit of a PEP 20 violation except the idea of simplicity is the self-contained nature.  I failed to make it actually self contained, since to be really useful it includes Jinja2 as an import.  If you choose to use a non WSGIRef server like Paste, Gevent, Waitress more imports will be required, be forwarned.

Now, that I've spent some time creating Minimus.  I can say it is "simple" to me now.  I started writing a framework around Python Paste https://pypi.org/project/Paste/, I got a bit of confidence that I wasn't wasting my time!  But, got a little sad learning that the author Chris Dent was not actively developing it!  So after some made some refactoring I jump started the application object as a generic WSGI app.

Quickly, I started cloning some of the Python decorator approaches of Flask and Bottle.  If you know Bottle or Flask, you will recognize that I cloned their decorator approach and some function names and approaches to solving templating. Of course, the Pallets project Jinja2 is (in my opinion) the absolute best of class templating engine.  I decided NOT to reinvent that wheel (for now).

So someone who codes Flask or Bottle could do some minor refactoring and have their app running on Minimus.

The "environ" MUST be passed into to every view.  The "environ" or WSGI environment is essential to a webapp and with each request will pass to the function.  That was a design choice that I feel Bottle and Flask are missing.  Django and Pyramid get it, but use a "Request" object to abstract it.  One of my friends suggested I use "WebOb" library, maybe they were correct... but this works too.

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

## Class Based Views

Minimus can support "Class based views."  This is currently developing and only (so far) supports GET, POST, PUT, and DELETE methods. If you wanted a Pony (Django), then get a Pony.

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

## Support for Jinja2 templates

Minimus also supports Jinja2 templates, much like Flask.  It was designed in a similar fashion to support keyword arguments like `name`.

If we had a template file like this...

```html
<!DOCTYPE html>
<html>
    <body>
        <h1>Hello There {{ name }}</h1>
        <p>Minimus is ready and waiting!</p>
    </body>
</html>
```

And we had a program like this...

```python
from minimus import Minimus, render_template

app = Minimus(__name__)

@app.route('/<name>')
def index(env, name):
    return render_template('index.html', name=name)
    
app.run()
```

Minimus is pretty capable of serving as your web framework.  If this is looking like Flask, yes definitely an homage.

## Forms Handling

We can handle forms very similar to Bottle and Flask.  This is going to look less like Flask and more like Pyramid and it's heritage of Paste.

```python
from minimus import Minimus, parse_formvars, redirect, parse_querystring

app = Minimus(__name__)

simple_form = """
<h1>My Form</h1>
<form method="post">
  Name<br />
  <input name="name" type="text"><br />
  
  Enter your message<br />
  <textarea name="message"></textarea><br />
  
  <input type="submit">
</form>
"""

@app.route('/')
def index(environ):
  return """<h1>Index</h1>
  <a href="/form">Send a Message</a><br>
  """
@app.route('/hello')
def hello(environ):
    args = parse_querystring(environ)
    return f"<h1>Hello</h1><p>Thanks for for the message:\n {args}.</p>"
    
@app.route('/form', methods=['GET', 'POST'])
def myform(environ):
    if environ.get('REQUEST_METHOD') == 'POST':
        fields = parse_formvars(environ)
        name = fields.get('name')
        message = fields.get('message')
        print(f"{name} said {message}")
        return redirect(f'/hello?name={name}&message={message}')
        
    return simple_form
    
app.run(host='0.0.0.0', port=5000)
```
        
So that's it for now.  I will improve the documentation and feel free to tear it apart, cut-and-paste, etc.  There are no guarantees you will see more documentation unless I get motivated.
