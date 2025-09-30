import gradio as gr
from fastapi import FastAPI

app = FastAPI()

interface1 = gr.Interface(lambda x: x, "text", "text")
interface2 = gr.Interface(lambda x: x.upper(), "text", "text")

app = gr.mount_gradio_app(app, interface1, path="/")
app = gr.mount_gradio_app(app, interface2, path="/test")

print('routes:', [r.path if hasattr(r, "path") else r.scope.get("path") for r in app.router.routes])

# we won't run uvicorn here
