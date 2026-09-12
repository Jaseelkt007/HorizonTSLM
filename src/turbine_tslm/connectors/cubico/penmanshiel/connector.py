from turbine_tslm.connectors.cubico.base import CubicoConnector


class PenmanshielConnector(CubicoConnector):
    FARM = "penmanshiel"
    PROVIDER_NAME = "Penmanshiel MM82 SCADA (Greenbyte export)"


CONNECTOR = PenmanshielConnector
