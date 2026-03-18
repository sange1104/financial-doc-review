from enum import Enum


class DocumentType(str, Enum):
    ID_CARD = "id_card"
    BANK_ACCOUNT_DOC = "bank_account_doc"
    UNKNOWN = "unknown"
