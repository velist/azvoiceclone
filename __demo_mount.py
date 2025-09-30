import gradio as gr
import uvicorn
from fastapi import FastAPI

blocks = gr.Interface(lambda x: f"Hello {x}", 'text', 'text')
app = FastAPI()
app = gr.mount_gradio_app(app, blocks, path="/admin")

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=7861)
