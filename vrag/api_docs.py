from fastapi.responses import RedirectResponse
def configure_api_docs(app):
    @app.get('/api-docs')
    def api_docs():
        return RedirectResponse(url='/docs')
