from turbine_tslm.connectors.cubico.base import CubicoConnector


class KelmarshConnector(CubicoConnector):
    FARM = "kelmarsh"
    PROVIDER_NAME = "Kelmarsh MM92 SCADA (Greenbyte export)"


CONNECTOR = KelmarshConnector
