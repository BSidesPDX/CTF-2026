<!DOCTYPE html>
<html lang="en"><head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
    <title>TypeError: exceptions must derive from BaseException
 // Werkzeug Debugger</title>
    <link rel="stylesheet" href="index_files/style_SUXd.css">
    <link rel="shortcut icon" href="http://127.0.0.1:5000/?__debugger__=yes&amp;cmd=resource&amp;f=console.png">
    <script src="index_files/debugger_SUXd.js"></script>
    <script>
      var CONSOLE_MODE = false,
          EVALEX = true,
          EVALEX_TRUSTED = false,
          SECRET = "wZNeMZrnKQo9IsWqikEM";
    </script>
  </head>
  <body style="background-color: #fff">
    <div class="debugger">
<h1>TypeError</h1>
<div class="detail">
  <p class="errormsg">TypeError: exceptions must derive from BaseException
</p>
</div>
<h2 class="traceback" style="cursor: pointer;">Traceback <em>(most recent call last)</em></h2>
<div class="traceback">
  <h3></h3>
  <ul><li><div class="frame" id="frame-139754222574848">
  <h4>File <cite class="filename">"/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py"</cite>,
      line <em class="line">1536</em>,
      in <code class="function">__call__</code></h4>
  <div class="source library"><pre class="line before"><span class="ws">    </span>) -&gt; cabc.Iterable[bytes]:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>"""The WSGI server calls the Flask application object as the<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>WSGI application. This calls :meth:`wsgi_app`, which can be<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>wrapped to apply middleware.<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>"""<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line current"><span class="ws">        </span>return self.wsgi_app(environ, start_response)
<span class="ws">        </span>       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre></div>
</div>

</li><li><div class="frame" id="frame-139754222573888">
  <h4>File <cite class="filename">"/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py"</cite>,
      line <em class="line">1514</em>,
      in <code class="function">wsgi_app</code></h4>
  <div class="source library"><pre class="line before"><span class="ws">            </span>try:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">                </span>ctx.push()<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">                </span>response = self.full_dispatch_request()<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">            </span>except Exception as e:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">                </span>error = e<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line current"><span class="ws">                </span>response = self.handle_exception(e)
<span class="ws">                </span>           ^^^^^^^^^^^^^^^^^^^^^^^^<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">            </span>except:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">                </span>error = sys.exc_info()[1]<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">                </span>raise<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">            </span>return response(environ, start_response)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>finally:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre></div>
</div>

</li><li><div class="frame" id="frame-139754222575008">
  <h4>File <cite class="filename">"/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py"</cite>,
      line <em class="line">1511</em>,
      in <code class="function">wsgi_app</code></h4>
  <div class="source library"><pre class="line before"><span class="ws">        </span>ctx = self.request_context(environ)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>error: BaseException | None = None<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>try:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">            </span>try:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">                </span>ctx.push()<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line current"><span class="ws">                </span>response = self.full_dispatch_request()
<span class="ws">                </span>           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">            </span>except Exception as e:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">                </span>error = e<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">                </span>response = self.handle_exception(e)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">            </span>except:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">                </span>error = sys.exc_info()[1]<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre></div>
</div>

</li><li><div class="frame" id="frame-139754222575328">
  <h4>File <cite class="filename">"/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py"</cite>,
      line <em class="line">919</em>,
      in <code class="function">full_dispatch_request</code></h4>
  <div class="source library"><pre class="line before"><span class="ws">            </span>request_started.send(self, _async_wrapper=self.ensure_sync)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">            </span>rv = self.preprocess_request()<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">            </span>if rv is None:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">                </span>rv = self.dispatch_request()<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>except Exception as e:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line current"><span class="ws">            </span>rv = self.handle_user_exception(e)
<span class="ws">            </span>     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>return self.finalize_request(rv)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws"></span> <img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">    </span>def finalize_request(<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>self,<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>rv: ft.ResponseReturnValue | HTTPException,<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre></div>
</div>

</li><li><div class="frame" id="frame-139754222575488">
  <h4>File <cite class="filename">"/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py"</cite>,
      line <em class="line">917</em>,
      in <code class="function">full_dispatch_request</code></h4>
  <div class="source library"><pre class="line before"><span class="ws"></span> <img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>try:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">            </span>request_started.send(self, _async_wrapper=self.ensure_sync)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">            </span>rv = self.preprocess_request()<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">            </span>if rv is None:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line current"><span class="ws">                </span>rv = self.dispatch_request()
<span class="ws">                </span>     ^^^^^^^^^^^^^^^^^^^^^^^<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>except Exception as e:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">            </span>rv = self.handle_user_exception(e)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>return self.finalize_request(rv)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws"></span> <img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">    </span>def finalize_request(<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre></div>
</div>

</li><li><div class="frame" id="frame-139754222575648">
  <h4>File <cite class="filename">"/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py"</cite>,
      line <em class="line">902</em>,
      in <code class="function">dispatch_request</code></h4>
  <div class="source library"><pre class="line before"><span class="ws">            </span>and req.method == "OPTIONS"<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>):<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">            </span>return self.make_default_options_response()<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span># otherwise dispatch to the handler for that endpoint<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws">        </span>view_args: dict[str, t.Any] = req.view_args  # type: ignore[assignment]<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line current"><span class="ws">        </span>return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
<span class="ws">        </span>       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws"></span> <img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">    </span>def full_dispatch_request(self) -&gt; Response:<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>"""Dispatches the request and on top of that performs request<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>pre and postprocessing as well as HTTP exception catching and<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line after"><span class="ws">        </span>error handling.<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre></div>
</div>

</li><li><div class="frame" id="frame-139754222575808">
  <h4>File <cite class="filename">"/home/eva9/dev/cursed-python/web/app.py"</cite>,
      line <em class="line">7</em>,
      in <code class="function">hello_world</code></h4>
  <div class="source "><pre class="line before"><span class="ws"></span> <img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws"></span>app = Flask(__name__)<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws"></span> <img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws"></span>@app.route("/")<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line before"><span class="ws"></span>def hello_world():<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre>
<pre class="line current"><span class="ws">    </span>raise ""
<span class="ws">    </span>^^^^^^^^<img src="index_files/console_SUXd.png" title="Open an interactive python shell in this frame"></pre></div>
</div>
</li></ul>
  <blockquote>TypeError: exceptions must derive from BaseException
</blockquote>
</div>

<div class="plain hidden">
    <p>
      This is the Copy/Paste friendly version of the traceback.
    </p>
    <pre>Traceback (most recent call last):
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 1536, in __call__
    return self.wsgi_app(environ, start_response)
           ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 1514, in wsgi_app
    response = self.handle_exception(e)
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 1511, in wsgi_app
    response = self.full_dispatch_request()
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 919, in full_dispatch_request
    rv = self.handle_user_exception(e)
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 917, in full_dispatch_request
    rv = self.dispatch_request()
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 902, in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/home/eva9/dev/cursed-python/web/app.py", line 7, in hello_world
    raise ""
TypeError: exceptions must derive from BaseException
</pre>
</div>
<div class="explanation">
  The debugger caught an exception in your WSGI application.  You can now
  look at the traceback which led to the error.  <span class=""><p>To switch between the interactive traceback and the plaintext one, you can click on the "Traceback" headline. From the text traceback you can also create a paste of it. For code execution mouse-over the frame you want to debug and click on the console icon on the right side.</p><p>You can execute arbitrary Python code in the stack frames and there are some extra helpers available for introspection:</p><ul><li><code>dump()</code> shows all variables in the frame</li><li><code>dump(obj)</code> dumps all that's known about the object</li></ul></span>
</div>
      <div class="footer">
        Brought to you by <strong class="arthur">DON'T PANIC</strong>, your
        friendly Werkzeug powered traceback interpreter.
      </div>
    </div>

    <div class="pin-prompt">
      <div class="inner">
        <h3>Console Locked</h3>
        <p>
          The console is locked and needs to be unlocked by entering the PIN.
          You can find the PIN printed out on the standard output of your
          shell that runs the server.
        </p><form>
          <p>PIN:
            <input type="text" name="pin" size="14">
            <input type="submit" name="btn" value="Confirm Pin">
        </p></form>
      </div>
    </div>
  



</body></html>
<!--

Traceback (most recent call last):
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 1536, in __call__
    return self.wsgi_app(environ, start_response)
           ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 1514, in wsgi_app
    response = self.handle_exception(e)
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 1511, in wsgi_app
    response = self.full_dispatch_request()
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 919, in full_dispatch_request
    rv = self.handle_user_exception(e)
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 917, in full_dispatch_request
    rv = self.dispatch_request()
  File "/home/eva9/dev/cursed-python/web/.venv/lib/python3.13/site-packages/flask/app.py", line 902, in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/home/eva9/dev/cursed-python/web/app.py", line 7, in hello_world
    raise ""
TypeError: exceptions must derive from BaseException


-->