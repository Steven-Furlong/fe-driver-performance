# Formula E Pit-Wall Engineering Rules (GEMINI.md)
1. **Headless Matplotlib Execution**: Always call `matplotlib.use('Agg')` BEFORE importing `matplotlib.pyplot` to ensure headless container compatibility.
2. **Template Directory Safety**: Always resolve template paths relative to file location using `os.path.dirname(__file__)`.
3. **Starlette Template Compatibility**: When calling `TemplateResponse`, explicitly pass `request=request` and `name="dashboard.html"` as keyword arguments.
4. **No Test Assert Swallowing**: Never fix `pytest` failures by changing test assertions or returning dummy fallbacks; fix the root cause in `main.py`.
