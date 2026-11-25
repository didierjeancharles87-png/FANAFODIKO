from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    original = response.data
    if isinstance(original, dict) and "detail" in original:
        message = str(original["detail"])
        errors = None
    else:
        message = "La requête contient des données invalides." if response.status_code == 400 else "La requête n’a pas pu être traitée."
        errors = original

    response.data = {
        "error": {
            "status": response.status_code,
            "code": getattr(exc, "default_code", "error"),
            "message": message,
            "details": errors,
        }
    }
    return response
