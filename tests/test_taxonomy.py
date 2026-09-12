from turbine_tslm.data.taxonomy import UNMAPPED, classify, fault_classes


def test_known_messages_map_to_expected_classes():
    assert classify("Overload generator fan 2") == ("generator_cooling", "fault")
    assert classify("Low gearbox oil pressure") == ("gearbox_lubrication", "fault")
    assert classify("Wind < start wind") == ("environmental_stop", "benign")
    assert classify("Manual stop - on site") == ("manual_safety", "context")
    assert classify("Battery test") == ("routine_operation", "context")


def test_unknown_message_is_unmapped_not_an_error():
    assert classify("Something the controller never said") == (UNMAPPED, "unknown")


def test_fault_classes_exclude_benign_and_context():
    fc = fault_classes()
    assert "generator_cooling" in fc and "manual_safety" not in fc and "environmental_stop" not in fc
