from django.contrib.auth.hashers import PBKDF2PasswordHasher


class PBKDF2Hasher600k(PBKDF2PasswordHasher):
    """
    PBKDF2-SHA256 con 600 000 iteraciones, el mínimo que recomienda OWASP para
    este algoritmo (RNF-15). Django usa 1 000 000: en el servidor modesto
    previsto para la entidad, cada inicio de sesión ocupaba un núcleo de CPU
    durante más de 1,5 s y varios inicios simultáneos superaban el límite de
    3 s de RNF-04. Las contraseñas existentes se actualizan solas al ingresar.
    """

    iterations = 600_000
