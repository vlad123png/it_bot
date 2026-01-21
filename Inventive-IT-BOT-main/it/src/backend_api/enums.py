from enum import StrEnum


class ReactionType(StrEnum):
    like = 'like'
    dislike = 'dislike'


class Index(StrEnum):
    MANUALS_1C = 'manuals_1c'
    ARED_HELP = 'ared_help'
    HELP = 'help'
    SAP_ERP = 'sap_erp'
    DOCUMENT_FLOW_1C = 'document_flow_1c'
    SBIS = 'sbis'
    UPP = 'upp'
