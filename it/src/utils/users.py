from src.backend_api.schemas import BackendUserSchema


__all__ = ('is_ared', 'match_user')



def is_ared(email: str) -> bool:
    domen = email.split('@')[1]
    return domen == 'amazingred.ru'

def match_user(inventive_name: str, backend_user: BackendUserSchema) -> bool:
    """
    inventive_name – строка вида «Иванов Иван Иванович» (любой регистр).
    backend_user – объект с полями .name и .surname.
    """
    inventive_tokens = {t.lower() for t in inventive_name.split()}
    return (
        backend_user.name.lower() in inventive_tokens
        and backend_user.surname.lower() in inventive_tokens
    )
