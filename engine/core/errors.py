"""Errores de dominio del núcleo."""


class TransitionError(Exception):
    """La arista no existe o una regla extra la rechazó. No persiste cambios."""


class DuplicateLeadError(Exception):
    """Nombre normalizado y comuna ya existen en un lead no anonimizado."""
