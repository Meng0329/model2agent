---
name: gradio-ui-generation
description: Build the ChatGPT-style Gradio web interface for the generated Model Agent, matching the Model2Agent light minimal design system. Use during agent-generation.
---
# Gradio UI Generation

UI must match the Model2Agent design system: white/light-gray, teal accent, soft
borders, uniform radius, generous whitespace. Adapt the input control to the
model's verified input type:
- image model  -> gr.Image upload + prediction display
- table model  -> gr.File (CSV) upload + batch prediction table
- text model   -> gr.Textbox + result display
Use gr.Chatbot(type="messages") for multi-turn chat and gr.Code for file preview.
Do not invent input/output types the model cannot actually handle.
