"""Errores de adaptadores. La firma inválida se traduce a 401 en la API."""


class WebhookSignatureError(Exception):
    """La firma no calza con el secreto. No se procesa el cuerpo."""


class ProviderRequestError(Exception):
    """El proveedor no confirmó la operación. No hay pago ni publicación."""
