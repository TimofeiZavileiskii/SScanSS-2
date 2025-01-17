import json
from collections import namedtuple
import unittest
import unittest.mock as mock
import numpy as np
from PyQt5.QtWidgets import QLineEdit, QComboBox, QDoubleSpinBox
from sscanss.core.instrument.instrument import Instrument, PositioningStack, Detector, Script, Jaws
from sscanss.core.instrument.robotics import Link, SerialManipulator
from sscanss.editor.main import EditorWindow
from sscanss.editor.widgets import PositionerWidget, JawsWidget, ScriptWidget, DetectorWidget
from sscanss.editor.designer import (Designer, VisualSubComponent, GeneralComponent, JawComponent, DetectorComponent,
                                     CollimatorComponent, FixedHardwareComponent, PositioningStacksComponent)
from sscanss.editor.dialogs import CalibrationWidget, Controls, FindWidget
from tests.helpers import TestSignal, APP, SAMPLE_IDF

Collimator = namedtuple("Collimator", ["name"])


class TestEditor(unittest.TestCase):
    @mock.patch("sscanss.editor.view.SceneManager", autospec=True)
    def setUp(self, scene_mock):
        self.view = EditorWindow()
        self.view.animate_instrument = TestSignal()
        self.view.presenter.model.saved_text = ""
        self.view.presenter.model.instrument = mock.create_autospec(Instrument)

        q1 = Link("", [1.0, 0.0, 0.0], [0.0, 0.0, 0.0], Link.Type.Prismatic, 0, 100, 0)
        q2 = Link("", [0.0, 0.0, 1.0], [0.0, 0.0, 0.0], Link.Type.Prismatic, 0, 100, 0)
        q3 = Link("", [0.0, 0.0, -1.0], [0.0, 0.0, 0.0], Link.Type.Revolute, -3.14, 3.14, 0)

        s1 = PositioningStack("a", SerialManipulator("a", [q1, q2]))
        s1.addPositioner(SerialManipulator("c", [q3]))
        s2 = PositioningStack("b", SerialManipulator("b", [q2, q1]))

        self.view.presenter.model.instrument.positioning_stacks = {s1.name: s1, s2.name: s2}
        self.view.presenter.model.instrument.positioning_stack = s1
        self.view.presenter.model.instrument.jaws = Jaws("", [0, 0, 0], [1, 0, 0], [1.0, 1.0], [0.5, 0.5], [4.0, 4.0],
                                                         None)
        self.view.presenter.model.instrument.detectors = {"East": Detector("East", [1, 0, 0])}
        self.view.presenter.model.instrument.script = Script(
            "{{header}}\n{{#script}}\n{{position}}    {{mu_amps}}\n{{/script}}")

    def testPositionerWidget(self):
        widget = PositionerWidget(self.view)
        widget.changeStack("b")
        self.view.presenter.model.instrument.loadPositioningStack.assert_called_with("b")

        self.assertEqual(self.view.presenter.model.instrument.positioning_stack.set_points[0], 0)
        widget.positioner_form_controls[0].setValue(50)
        widget.move_joints_button.click()
        self.assertEqual(self.view.presenter.model.instrument.positioning_stack.set_points[0], 50)

    def testFindInText(self):
        # Testing search works, and only finds one occurrence
        window = self.view
        window.editor.setText("The Text")
        widget = FindWidget(window)
        widget.search_box.setText("text")
        widget.search()
        self.assertEqual(window.editor.selectedText(), "Text")
        widget.search()
        self.assertEqual(widget.status_box.text(), "No more entries found.")
        # Testing match case
        window.editor.selectAll(False)
        widget.match_case.click()
        widget.search()
        self.assertNotEqual(window.editor.selectedText(), "Text")
        widget.search_box.setText("Text")
        window.editor.selectAll(False)
        widget.search()
        self.assertEqual(window.editor.selectedText(), "Text")
        widget.match_case.click()
        # Testing whole word
        widget.whole_word.click()
        window.editor.selectAll(False)
        widget.search()
        self.assertEqual(window.editor.selectedText(), "Text")
        widget.search_box.setText("Tex")
        window.editor.selectAll(False)
        widget.search()
        self.assertNotEqual(window.editor.selectedText(), "Text")
        widget.whole_word.click()
        # Testing empty search string
        window.editor.setText("The Text")
        widget.search_box.setText("")
        window.editor.selectAll(False)
        widget.search()
        self.assertEqual(widget.status_box.text(), "No more entries found.")
        # Testing empty search string and empty window text
        window.editor.setText("")
        widget.search_box.setText("")
        window.editor.selectAll(False)
        widget.search()
        self.assertEqual(widget.status_box.text(), "No more entries found.")

    def testJawsWidget(self):
        widget = JawsWidget(self.view)
        self.assertEqual(widget.aperture_forms[0].value(), 1)
        widget.aperture_forms[0].setValue(3)
        widget.change_aperture_button.click()
        self.assertEqual(widget.aperture_forms[0].value(), 3)

        q1 = Link("", [1.0, 0.0, 0.0], [0.0, 0.0, 0.0], Link.Type.Prismatic, 0, 100, 0)
        q2 = Link("", [0.0, 0.0, -1.0], [0.0, 0.0, 0.0], Link.Type.Revolute, -3.14, 3.14, 0)
        self.view.presenter.model.instrument.jaws.positioner = SerialManipulator("a", [q1, q2])
        widget = JawsWidget(self.view)
        self.assertEqual(self.view.presenter.model.instrument.jaws.positioner.set_points[0], 0)
        widget.position_forms[0].setValue(50)
        widget.move_jaws_button.click()
        self.assertEqual(self.view.presenter.model.instrument.jaws.positioner.set_points[0], 50)

    def testDetectorWidget(self):
        widget = DetectorWidget(self.view, "East")
        self.assertEqual(widget.collimator_name, "None")

        c = {"1": Collimator("1"), "2": Collimator("2")}
        self.view.presenter.model.instrument.detectors = {"East": Detector("East", [1, 0, 0], c)}

        widget = DetectorWidget(self.view, "East")
        widget.combobox.setCurrentIndex(1)
        widget.changeCollimator()
        self.assertEqual(widget.collimator_name, "1")

        q1 = Link("", [1.0, 0.0, 0.0], [0.0, 0.0, 0.0], Link.Type.Prismatic, 0, 100, 0)
        q2 = Link("", [0.0, 0.0, -1.0], [0.0, 0.0, 0.0], Link.Type.Revolute, -3.14, 3.14, 0)
        positioner = SerialManipulator("a", [q1, q2])
        self.view.presenter.model.instrument.detectors = {"East": Detector("East", [1, 0, 0], c, positioner)}
        widget = DetectorWidget(self.view, "East")

        self.assertEqual(self.view.presenter.model.instrument.detectors["East"].positioner.set_points[0], 0)
        widget.position_forms[0].setValue(50)
        widget.move_detector_button.click()
        self.assertEqual(self.view.presenter.model.instrument.detectors["East"].positioner.set_points[0], 50)

    def testScriptWidget(self):
        widget = ScriptWidget(self.view)
        self.assertNotEqual(widget.preview_label.toPlainText(), "")
        widget.updateScript()

        self.view.presenter.model.instrument.script = Script("{{header}}\n{{#script}}\n{{position}}\n{{/script}}")
        self.widget = ScriptWidget(self.view)
        self.assertNotEqual(widget.preview_label.toPlainText(), "")

    def testControlsDialog(self):
        widget = Controls(self.view)
        widget.createWidgets()
        self.assertEqual(self.view.presenter.model.instrument.positioning_stack.name, "a")
        self.assertEqual(widget.last_stack_name, "")
        widget.setStack("b")
        widget.createWidgets()
        self.assertEqual(widget.last_stack_name, "b")

        self.assertDictEqual(widget.last_collimator_name, {})
        widget.setCollimator("East", "1")
        widget.createWidgets()
        self.assertDictEqual(widget.last_collimator_name, {"East": "1"})

        self.assertEqual(widget.last_tab_index, 0)
        self.view.presenter.model.instrument.script = Script("{{header}}\n{{#script}}\n{{position}}\n{{/script}}")
        text = widget.script_widget.preview_label.toPlainText()
        widget.updateTabs(3)
        widget.createWidgets()
        self.assertEqual(widget.last_tab_index, 3)
        self.assertNotEqual(text, widget.script_widget.preview_label.toPlainText())

        widget.reset()
        self.assertEqual(widget.last_stack_name, "")
        self.assertDictEqual(widget.last_collimator_name, {})
        self.assertEqual(widget.last_tab_index, 0)

    @mock.patch("sscanss.editor.dialogs.QtWidgets.QFileDialog", autospec=True)
    def testCalibrationDialog(self, file_dialog):
        points = [
            np.array([[12.0, 0.0, 2.5], [10.0, 2.0, 1.5], [8.0, 0.0, 1.5]]),
            np.array([[10.0, 0.0, 1.5], [11.0, -1.0, 1.5], [12.0, 0.0, 1.5]]),
        ]

        offsets = [np.array([0.0, 90.0, 180.0]), np.array([-180.0, -90.0, 0.0])]
        types = [Link.Type.Revolute, Link.Type.Revolute]
        homes = np.array([10.0, 0.0])

        widget = CalibrationWidget(self.view, points, types, offsets, homes)
        widget.calibrate_button.click()

        line_edits = widget.findChildren(QLineEdit)

        line_edits[0].setText("")
        self.assertFalse(widget.calibrate_button.isEnabled())
        self.assertEqual(widget.robot_name, "")
        line_edits[0].setText("Two link")
        self.assertTrue(widget.calibrate_button.isEnabled())
        self.assertEqual(widget.robot_name, "Two link")

        line_edits[1].setText("")
        self.assertFalse(widget.calibrate_button.isEnabled())
        line_edits[1].setText("3, 1")
        self.assertListEqual(widget.order, [])
        self.assertFalse(widget.calibrate_button.isEnabled())
        line_edits[1].setText("b, a")
        self.assertListEqual(widget.order, [])
        self.assertFalse(widget.calibrate_button.isEnabled())
        line_edits[1].setText("3, 1, 2")
        self.assertListEqual(widget.order, [])
        self.assertFalse(widget.calibrate_button.isEnabled())
        line_edits[1].setText("2, 1")
        self.assertListEqual(widget.order, [1, 0])

        line_edits[2].setText("")
        self.assertFalse(widget.calibrate_button.isEnabled())
        self.assertEqual(widget.names[0], "")
        line_edits[2].setText("a")
        self.assertTrue(widget.calibrate_button.isEnabled())
        line_edits[4].setText("a")
        self.assertFalse(widget.calibrate_button.isEnabled())
        line_edits[4].setText("b")
        self.assertTrue(widget.calibrate_button.isEnabled())
        self.assertEqual(widget.names[0], "a")

        self.assertEqual(widget.types[1], Link.Type.Revolute)
        widget.findChildren(QComboBox)[1].setCurrentIndex(1)
        self.assertEqual(widget.types[1], Link.Type.Prismatic)

        self.assertEqual(widget.homes[0], 10.0)
        widget.findChildren(QDoubleSpinBox)[0].setValue(0.0)
        self.assertEqual(widget.homes[0], 0.0)

        self.assertEqual(widget.model_error_table.rowCount(), 6)
        widget.filter_combobox.setCurrentIndex(1)
        self.assertEqual(widget.model_error_table.rowCount(), 3)
        widget.tabs.setCurrentIndex(1)
        self.assertEqual(widget.fit_error_table.rowCount(), 3)
        widget.filter_combobox.setCurrentIndex(0)
        self.assertEqual(widget.fit_error_table.rowCount(), 6)

        widget.json = {"name": "Json"}
        widget.copy_model_button.click()
        self.assertEqual("".join(APP.clipboard().text().split()), '{"name":"Json"}')

        file_dialog.getSaveFileName.return_value = ("", "")
        widget.save_model_button.click()
        file_dialog.getSaveFileName.return_value = ("file.json", "")
        m = mock.mock_open()
        with mock.patch("sscanss.editor.dialogs.open", m):
            widget.save_model_button.click()
            m.assert_called_once()

    def testDesigner(self):
        widget = Designer(self.view)
        widget.json_updated = TestSignal()
        mock_func = mock.Mock()
        widget.json_updated.connect(mock_func)

        widget.setJson({})
        widget.updateJson()
        mock_func.assert_not_called()

        self.assertIsNone(widget.component)
        widget.setComponent(Designer.Component.Jaws)
        self.assertIsNotNone(widget.component)

        widget.setJson({})
        widget.updateJson()
        mock_func.assert_not_called()
        self.assertFalse(widget.component.validate())

        json_data = json.loads(SAMPLE_IDF)
        widget.setJson(json_data)
        self.assertTrue(widget.component.validate())

        self.assertEqual(widget.component.positioner_combobox.currentText(), 'incident_jaws')
        widget.component.positioner_combobox.setCurrentText('None')
        widget.updateJson()
        mock_func.assert_called_with(json_data)
        self.assertIsNone(json_data['instrument']['incident_jaws'].get('positioner'))

        widget.setComponent(Designer.Component.General)
        widget.setJson(json_data)
        self.assertEqual(widget.component.instrument_name.text(), 'GENERIC')
        self.assertTrue(widget.component.validate())
        widget.component.y_gauge_volume.setText('')
        self.assertFalse(widget.component.validate())
        widget.component.y_gauge_volume.setText('1.0')
        self.assertTrue(widget.component.validate())
        widget.updateJson()
        self.assertListEqual(json_data['instrument']['gauge_volume'], [0, 1, 0])

        widget.clear()
        self.assertEqual(widget.folder_path, '.')
        self.assertDictEqual(widget.json, {})
        self.assertEqual(widget.folder_path, '.')

    def testVisualComponent(self):
        component = VisualSubComponent()
        pose_widgets = [
            component.x_translation, component.y_translation, component.z_translation, component.x_orientation,
            component.y_orientation, component.z_orientation
        ]
        for widget in pose_widgets:
            self.assertEqual(widget.text(), '0.0')
        self.assertEqual(component.colour_picker.value.name(), '#000000')
        self.assertEqual(component.file_picker.value, '')

        component.updateValue({}, '')
        for widget in pose_widgets:
            self.assertEqual(widget.text(), '0.0')
        self.assertEqual(component.colour_picker.value.name(), '#000000')
        self.assertEqual(component.file_picker.value, '')
        self.assertEqual(component.validation_label.text(), '')
        self.assertFalse(component.validate())
        self.assertDictEqual(component.value()[component.key], {})
        self.assertNotEqual(component.validation_label.text(), '')

        json_data = {"mesh": "../instruments/engin-x/models/beam_guide.stl"}
        component.updateValue(json_data, '.')
        for widget in pose_widgets:
            self.assertEqual(widget.text(), '0.0')
        self.assertEqual(component.colour_picker.value.name(), '#000000')
        self.assertEqual(component.file_picker.value, '../instruments/engin-x/models/beam_guide.stl')
        self.assertTrue(component.validate())
        self.assertEqual(component.validation_label.text(), '')
        self.assertDictEqual(component.value(), {"visual": json_data})

        json_data = {
            "pose": [1, 2, 3, 4, 5, 6],
            "colour": [1., 1., 1.],
            "mesh": "../instruments/engin-x/models/beam_guide.stl"
        }
        component.updateValue(json_data, '.')
        for index, widget in enumerate(pose_widgets):
            self.assertEqual(widget.text(), f'{json_data["pose"][index]:.1f}')
        self.assertEqual(component.colour_picker.value.name(), '#ffffff')
        self.assertEqual(component.file_picker.value, '../instruments/engin-x/models/beam_guide.stl')
        self.assertTrue(component.validate())
        self.assertDictEqual(component.value(), {"visual": json_data})

    def testGeneralComponent(self):
        component = GeneralComponent()
        widgets = [
            component.instrument_name, component.file_version, component.x_gauge_volume, component.y_gauge_volume,
            component.z_gauge_volume
        ]
        labels = [
            component.name_validation_label, component.version_validation_label, component.gauge_vol_validation_label
        ]
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.script_picker.value, '')

        component.updateValue({}, '')
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.script_picker.value, '')
        for label in labels:
            self.assertEqual(label.text(), '')
        self.assertFalse(component.validate())
        self.assertDictEqual(component.value(), {})
        for label in labels:
            self.assertNotEqual(label.text(), '')

        json_data = {'instrument': {'name': 'test', 'version': '1.2', 'gauge_volume': [1, 2, 3]}}
        result = ['test', '1.2', '1.0', '2.0', '3.0']
        component.updateValue(json_data, '')
        for index, widget in enumerate(widgets):
            self.assertEqual(widget.text(), result[index])
        self.assertEqual(component.script_picker.value, '')
        self.assertTrue(component.validate())
        self.assertDictEqual(component.value(), json_data['instrument'])
        for label in labels:
            self.assertEqual(label.text(), '')

        json_data['instrument']['script_template'] = 'script_template'
        component.updateValue(json_data, '')
        self.assertTrue(component.validate())
        self.assertEqual(component.script_picker.value, 'script_template')
        self.assertDictEqual(component.value(), json_data['instrument'])

    def testJawComponent(self):
        component = JawComponent()
        widgets = [
            component.x_aperture, component.y_aperture, component.x_aperture_lower_limit,
            component.y_aperture_lower_limit, component.x_aperture_upper_limit, component.y_aperture_upper_limit,
            component.x_beam_source, component.y_beam_source, component.z_beam_source, component.x_beam_direction,
            component.y_beam_direction, component.z_beam_direction
        ]
        labels = [
            component.aperture_validation_label, component.aperture_lo_validation_label,
            component.aperture_up_validation_label, component.beam_src_validation_label,
            component.beam_dir_validation_label
        ]
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.positioner_combobox.currentText(), 'None')

        component.updateValue({}, '')
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.positioner_combobox.currentText(), 'None')
        self.assertEqual(component.visuals.file_picker.value, '')
        for label in labels:
            self.assertEqual(label.text(), '')
        self.assertEqual(component.visuals.validation_label.text(), '')
        self.assertFalse(component.validate())
        self.assertDictEqual(component.value()[component.key], {})
        for label in labels:
            self.assertNotEqual(label.text(), '')
        self.assertNotEqual(component.visuals.validation_label.text(), '')

        json_data = {
            "instrument": {
                "incident_jaws": {
                    "aperture": [1.0, 1.0],
                    "aperture_lower_limit": [2.0, 2.0],
                    "aperture_upper_limit": [3.0, 3.0],
                    "beam_source": [1.0, 2.0, 3.0],
                    "beam_direction": [4.0, 5.0, 6.0],
                    "visual": {
                        "mesh": "beam_guide.stl"
                    }
                }
            }
        }

        result = ['1.0', '1.0', '2.0', '2.0', '3.0', '3.0', "1.0", "2.0", "3.0", "4.0", "5.0", "6.0"]
        component.updateValue(json_data, '')
        for index, widget in enumerate(widgets):
            self.assertEqual(widget.text(), result[index])
        self.assertEqual(component.positioner_combobox.currentText(), 'None')
        self.assertEqual(component.visuals.file_picker.value, 'beam_guide.stl')
        self.assertTrue(component.validate())
        self.assertDictEqual(component.value(), json_data['instrument'])
        for label in labels:
            self.assertEqual(label.text(), '')
        self.assertEqual(component.visuals.validation_label.text(), '')

        json_data = json.loads(SAMPLE_IDF)
        component.updateValue(json_data, '')
        self.assertTrue(component.validate())
        self.assertEqual(component.positioner_combobox.currentText(), 'incident_jaws')
        self.assertEqual(component.visuals.file_picker.value, 'model_path')
        self.assertDictEqual(component.value()[component.key], json_data['instrument'][component.key])

    def testDetectorComponent(self):
        component = DetectorComponent()
        widgets = [component.x_diffracted_beam, component.y_diffracted_beam, component.z_diffracted_beam]
        labels = [component.name_validation_label, component.diffracted_beam_validation_label]

        # Test text fields are empty to begin with
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.detector_name_combobox.currentText(), '')
        self.assertEqual(component.default_collimator_combobox.currentText(), 'None')
        self.assertEqual(component.positioner_combobox.currentText(), 'None')

        # Test inputting empty JSON data and updating the component.
        component.updateValue({}, '')
        # 1) The fields in the component should remain empty
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.detector_name_combobox.currentText(), '')
        self.assertEqual(component.default_collimator_combobox.currentText(), 'None')
        self.assertEqual(component.positioner_combobox.currentText(), 'None')
        for label in labels:
            self.assertEqual(label.text(), '')
        # 2) The component value should be updated to match the input
        self.assertCountEqual(component.value()[component.key], [{}])
        # 3) The component should not be declared valid -- because required arguments are not provided
        self.assertFalse(component.validate())
        # 4) The label text should not remain empty -- it should give a warning about the required fields
        for label in labels:
            self.assertNotEqual(label.text(), '')

        # Test inputting JSON data defined below and updating the component.
        # There are two detectors, each associated with two collimators
        json_data = {
            'instrument': {
                "detectors": [{
                    "name": "North",
                    "default_collimator": "2.0mm",
                    "diffracted_beam": [0.0, 1.0, 0.0]
                }, {
                    "name": "South",
                    "default_collimator": "2.0mm",
                    "diffracted_beam": [0.0, -1.0, 0.0]
                }],
                "collimators": [
                    {
                        "name": "1.0mm",
                        "detector": "South",
                        "aperture": [1.0, 200.0],
                        "visual": {
                            "pose": [0.0, 0.0, 0.0, 0.0, 0.0, 90.0],
                            "mesh": "models/collimator_1mm.stl",
                            "colour": [0.6, 0.6, 0.6]
                        }
                    },
                    {
                        "name": "2.0mm",
                        "detector": "South",
                        "aperture": [2.0, 200.0],
                        "visual": {
                            "pose": [0.0, 0.0, 0.0, 0.0, 0.0, 90.0],
                            "mesh": "models/collimator_2mm.stl",
                            "colour": [0.6, 0.6, 0.6]
                        }
                    },
                    {
                        "name": "1.0mm",
                        "detector": "North",
                        "aperture": [1.0, 200.0],
                        "visual": {
                            "pose": [0.0, 0.0, 0.0, 0.0, 0.0, -90.0],
                            "mesh": "models/collimator_1mm.stl",
                            "colour": [0.6, 0.6, 0.6]
                        }
                    },
                    {
                        "name": "2.0mm",
                        "detector": "North",
                        "aperture": [2.0, 200.0],
                        "visual": {
                            "pose": [0.0, 0.0, 0.0, 0.0, 0.0, -90.0],
                            "mesh": "models/collimator_2mm.stl",
                            "colour": [0.6, 0.6, 0.6]
                        }
                    },
                ]
            }
        }

        north_diffracted_beam = ['0.0', '1.0', '0.0']
        # This should select the first detector
        component.updateValue(json_data, '')
        # 1) The fields in the component should be updated to match the expected result
        for index, widget in enumerate(widgets):
            self.assertEqual(widget.text(), north_diffracted_beam[index])
        self.assertEqual(component.detector_name_combobox.currentText(), 'North')
        # 2) The component value should be updated to match the input
        self.assertCountEqual(component.value()[component.key], json_data['instrument'][component.key])
        # 3) The component should be declared valid -- all required arguments are specified
        self.assertTrue(component.validate())
        # 4) The label text should remain empty -- as the component is valid
        for label in labels:
            self.assertEqual(label.text(), '')

        south_diffracted_beam = ['0.0', '-1.0', '0.0']
        # If we switch detector, this should be recorded in the component
        component.detector_name_combobox.setCurrentIndex(1)
        component.detector_name_combobox.activated.emit(1)
        # 1) The fields in the component should be updated to match the expected result
        for index, widget in enumerate(widgets):
            self.assertEqual(widget.text(), south_diffracted_beam[index])
        self.assertEqual(component.detector_name_combobox.currentText(), 'South')

        # If we rename the detector in the component, the detector name should be updated in the collimators
        new_names = ['West', 'West', 'North', 'North']
        collimators = json_data.get('instrument').get('collimators')
        component.detector_name_combobox.setCurrentText('West')
        json_data['instrument'].update(component.value())
        component.updateValue(json_data, '')
        # 1) The fields in the component should be updated to match the expected result
        for index, widget in enumerate(widgets):
            self.assertEqual(widget.text(), south_diffracted_beam[index])
        self.assertEqual(component.detector_name_combobox.currentText(), 'West')
        # 2) The collimators associated with this detector should have their names updated
        for index, collimator in enumerate(collimators):
            self.assertEqual(collimator['detector'], new_names[index])

        # If we switch to the "Add New..." option, text fields should be cleared
        component.detector_name_combobox.setCurrentIndex(2)
        component.detector_name_combobox.activated.emit(1)
        # 1) The fields in the component should be cleared
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.detector_name_combobox.currentText(), '')
        self.assertEqual(component.default_collimator_combobox.currentText(), 'None')
        self.assertEqual(component.positioner_combobox.currentText(), 'None')
        for label in labels:
            self.assertEqual(label.text(), '')
        # 2) The component should not be declared valid -- because required arguments are not provided
        self.assertFalse(component.validate())
        # 3) The label text should not remain empty -- it should give a warning about the required fields
        for label in labels:
            self.assertNotEqual(label.text(), '')

        # Add a new detector
        component.detector_name_combobox.setCurrentText('East')
        component.x_diffracted_beam.setText('1.0')
        component.y_diffracted_beam.setText('0.0')
        component.z_diffracted_beam.setText('0.0')
        json_data['instrument'].update(component.value())
        component.updateValue(json_data, '')
        # 4) When adding the detector, it should appear in the JSON
        detectors = json_data.get('instrument').get('detectors')
        new_detectors = ['North', 'West', 'East']
        for index, detector in enumerate(detectors):
            self.assertEqual(detector['name'], new_detectors[index])

    def testCollimatorComponent(self):
        component = CollimatorComponent()
        widgets = [component.collimator_name, component.x_aperture, component.y_aperture]
        labels = [
            component.name_validation_label, component.detector_validation_label, component.aperture_validation_label,
            component.visuals.validation_label
        ]

        # Test text fields are empty to begin with
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.visuals.file_picker.value, '')
        self.assertEqual(component.collimator_combobox.currentText(), '')
        self.assertEqual(component.detector_combobox.currentText(), '')

        # Test inputting empty JSON data and updating the component.
        component.updateValue({}, '')
        # 1) The fields in the component should remain empty
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.visuals.file_picker.value, '')
        self.assertEqual(component.collimator_combobox.currentText(), component.add_new_text)
        self.assertEqual(component.detector_combobox.currentText(), '')
        for label in labels:
            self.assertEqual(label.text(), '')
        # 2) The component value should be updated to match the input
        self.assertCountEqual(component.value()[component.key], [{}])
        # 3) The component should not be declared valid -- because required arguments are not provided
        self.assertFalse(component.validate())
        # 4) The label text should not remain empty -- it should give a warning about the required fields
        for label in labels:
            self.assertNotEqual(label.text(), '')

        # Test inputting JSON data defined below and updating the component.
        # There are two detectors, each associated with two collimators
        json_data = {
            'instrument': {
                "detectors": [{
                    "name": "North",
                    "default_collimator": "2.0mm",
                    "diffracted_beam": [0.0, 1.0, 0.0]
                }, {
                    "name": "South",
                    "default_collimator": "2.0mm",
                    "diffracted_beam": [0.0, -1.0, 0.0]
                }],
                "collimators": [
                    {
                        "name": "1.0mm",
                        "detector": "South",
                        "aperture": [1.0, 200.0],
                        "visual": {
                            "pose": [0.0, 0.0, 0.0, 0.0, 0.0, 90.0],
                            "mesh": "models/collimator_1mm.stl",
                            "colour": [0.6, 0.6, 0.6]
                        }
                    },
                    {
                        "name": "2.0mm",
                        "detector": "South",
                        "aperture": [2.0, 200.0],
                        "visual": {
                            "pose": [0.0, 0.0, 0.0, 0.0, 0.0, 90.0],
                            "mesh": "models/collimator_2mm.stl",
                            "colour": [0.6, 0.6, 0.6]
                        }
                    },
                    {
                        "name": "1.0mm",
                        "detector": "North",
                        "aperture": [1.0, 200.0],
                        "visual": {
                            "pose": [0.0, 0.0, 0.0, 0.0, 0.0, -90.0],
                            "mesh": "models/collimator_1mm.stl",
                            "colour": [0.6, 0.6, 0.6]
                        }
                    },
                    {
                        "name": "2.0mm",
                        "detector": "North",
                        "aperture": [2.0, 200.0],
                        "visual": {
                            "pose": [0.0, 0.0, 0.0, 0.0, 0.0, -90.0],
                            "mesh": "models/collimator_2mm.stl",
                            "colour": [0.6, 0.6, 0.6]
                        }
                    },
                ]
            }
        }

        first_collimator = ['1.0mm', '1.0', '200.0']
        # This should select the first collimator
        component.updateValue(json_data, '')
        # 1) The fields in the component should be updated to match the expected result
        for index, widget in enumerate(widgets):
            self.assertEqual(widget.text(), first_collimator[index])
        self.assertEqual(component.collimator_combobox.currentText(), 'Collimator 1')
        self.assertEqual(component.detector_combobox.currentText(), 'South')
        self.assertEqual(component.visuals.file_picker.value, 'models/collimator_1mm.stl')
        # 2) The component value should be updated to match the input
        self.assertCountEqual(component.value()[component.key], json_data['instrument'][component.key])
        # 3) The component should be declared valid -- all required arguments are specified
        self.assertTrue(component.validate())
        # 4) The label text should remain empty -- as the component is valid
        for label in labels:
            self.assertEqual(label.text(), '')

        fourth_collimator = ['2.0mm', '2.0', '200.0']
        # If we switch collimator, this should be recorded in the component
        component.collimator_combobox.setCurrentIndex(3)
        component.collimator_combobox.activated.emit(1)
        # 1) The fields in the component should be updated to match the expected result
        for index, widget in enumerate(widgets):
            self.assertEqual(widget.text(), fourth_collimator[index])
        self.assertEqual(component.collimator_combobox.currentText(), 'Collimator 4')
        self.assertEqual(component.detector_combobox.currentText(), 'North')
        self.assertEqual(component.visuals.file_picker.value, 'models/collimator_2mm.stl')

        # If we switch the detector, this should be recorded in the component
        detector_list = [component.detector_combobox.itemText(i) for i in range(component.detector_combobox.count())]
        json_data['instrument']['collimators'][3]['detector'] = 'South'
        component.updateValue(json_data, '')
        # 1) The detector combobox should read the value of the new detector, with all detectors in the combobox
        self.assertEqual(component.detector_combobox.currentText(), 'South')
        for i in range(component.detector_combobox.count()):
            self.assertEqual(component.detector_combobox.itemText(i), detector_list[i])

        # If we add a new, unrecorded detector, this should not be included in the combobox
        new_detector = 'West'
        json_data['instrument']['collimators'][3]['detector'] = new_detector
        component.updateValue(json_data, '')
        # 1) The detector combobox should read the value of the new detector, but only contain the defined detectors
        self.assertEqual(component.detector_combobox.currentText(), new_detector)
        for i in range(component.detector_combobox.count()):
            self.assertEqual(component.detector_combobox.itemText(i), detector_list[i])

        # If we switch to the "Add New..." collimator option, text fields should be cleared
        component.collimator_combobox.setCurrentIndex(4)
        component.collimator_combobox.activated.emit(1)
        # 1) Most of the fields in the component should be cleared
        for widget in widgets:
            self.assertEqual(widget.text(), '')
        self.assertEqual(component.collimator_combobox.currentText(), component.add_new_text)
        self.assertEqual(component.visuals.file_picker.value, '')
        for label in labels:
            self.assertEqual(label.text(), '')
        # 2) The detector combobox should default to adding a new detector
        self.assertEqual(component.detector_combobox.currentText(), '')
        # 3) The component should not be declared valid -- because required arguments are not provided
        self.assertFalse(component.validate())
        # 4) The label text should not remain empty -- they should give warnings about the required fields
        for label in labels:
            self.assertNotEqual(label.text(), '')

        # Add a new collimator
        component.collimator_name.setText('3.0mm')
        component.x_aperture.setText('3.0')
        component.y_aperture.setText('200.0')
        json_data['instrument'].update(component.value())
        component.updateValue(json_data, '')
        # 5) When adding the detector, it should appear in the JSON
        collimators = json_data.get('instrument').get('collimators')
        new_collimators = ['1.0mm', '2.0mm', '1.0mm', '2.0mm', '3.0mm']
        for index, collimator in enumerate(collimators):
            self.assertEqual(collimator['name'], new_collimators[index])

    def testFixedHardwareComponent(self):
        component = FixedHardwareComponent()
        labels = [component.name_validation_label, component.visuals.validation_label]

        # Test text fields are empty to begin with
        self.assertEqual(component.name_combobox.currentText(), '')

        # Test inputting empty JSON data and updating the component.
        component.updateValue({}, '')
        # 1) The fields in the component should remain empty
        self.assertEqual(component.name_combobox.currentText(), '')
        self.assertEqual(component.visuals.file_picker.value, '')
        for label in labels:
            self.assertEqual(label.text(), '')
        # 2) The component value should be updated to match the input
        self.assertCountEqual(component.value()[component.key], [{}])
        # 3) The component should not be declared valid -- because required arguments are not provided
        self.assertFalse(component.validate())
        # 4) The label text should not remain empty -- it should give a warning about the required fields
        for label in labels:
            self.assertNotEqual(label.text(), '')

        # Test inputting JSON data defined below and updating the component.
        # There are three fixed hardware components
        json_data = {
            'instrument': {
                "fixed_hardware": [{
                    "name": "beam_stop",
                    "visual": {
                        "pose": [0.0, 0.0, -1730.0, 0.0, 0.0, 0.0],
                        "mesh": "models/beam_stop.stl",
                        "colour": [0.27, 0.57, 0.57]
                    }
                }, {
                    "name": "floor",
                    "visual": {
                        "pose": [0.0, 0.0, -2035.0, 0.0, 0.0, 0.0],
                        "mesh": "models/floor.stl",
                        "colour": [0.25, 0.51, 0.51]
                    }
                }, {
                    "name": "beam_guide",
                    "visual": {
                        "pose": [0.0, 0.0, -1730.0, 0.0, 0.0, 0.0],
                        "mesh": "models/beam_guide.stl",
                        "colour": [0.27, 0.57, 0.57]
                    }
                }]
            }
        }

        # This should select the first hardware component
        component.updateValue(json_data, '')
        # 1) The fields in the component should be updated to match the expected result
        self.assertEqual(component.name_combobox.currentText(), 'beam_stop')
        self.assertEqual(component.visuals.file_picker.value, 'models/beam_stop.stl')
        # 2) The component value should be updated to match the input
        self.assertCountEqual(component.value()[component.key], json_data['instrument'][component.key])
        # 3) The component should be declared valid -- all required arguments are specified
        self.assertTrue(component.validate())
        # 4) The label text should remain empty -- as the component is valid
        for label in labels:
            self.assertEqual(label.text(), '')

        # If we switch hardware component, this should be recorded in the component
        component.name_combobox.setCurrentIndex(1)
        component.name_combobox.activated.emit(1)
        # 1) The fields in the component should be updated to match the expected result
        self.assertEqual(component.name_combobox.currentText(), 'floor')
        self.assertEqual(component.visuals.file_picker.value, 'models/floor.stl')

        # If we switch to the "Add New..." option, text fields should be cleared
        component.name_combobox.setCurrentIndex(3)
        component.name_combobox.activated.emit(1)
        # 1) The fields in the component should be cleared
        self.assertEqual(component.name_combobox.currentText(), '')
        self.assertEqual(component.visuals.file_picker.value, '')
        for label in labels:
            self.assertEqual(label.text(), '')
        # 2) The component should not be declared valid -- because required arguments are not provided
        self.assertFalse(component.validate())
        # 3) The label text should not remain empty -- it should give a warning about the required fields
        for label in labels:
            self.assertNotEqual(label.text(), '')

        # Add new hardware
        component.name_combobox.setCurrentText('ceiling')
        json_data['instrument'].update(component.value())
        component.updateValue(json_data, '')
        # 4) When adding the hardware, it should appear in the JSON
        hardware = json_data.get('instrument').get('fixed_hardware')
        new_hardware = ['beam_stop', 'floor', 'beam_guide', 'ceiling']
        for index, hardware in enumerate(hardware):
            self.assertEqual(hardware['name'], new_hardware[index])

    def testPositioningStacksComponent(self):
        component = PositioningStacksComponent()
        labels = [component.name_validation_label, component.positioning_stack_validation_label]

        # Test text fields are empty to begin with
        self.assertEqual(component.name_combobox.currentText(), '')
        self.assertEqual(component.positioners_combobox.currentText(), '')
        self.assertEqual(component.positioning_stack_box.count(), 0)

        # Test inputting empty JSON data and updating the component.
        component.updateValue({}, '')
        # 1) The fields in the component should remain empty
        self.assertEqual(component.name_combobox.currentText(), '')
        self.assertEqual(component.positioners_combobox.currentText(), '')
        self.assertEqual(component.positioning_stack_box.count(), 0)
        for label in labels:
            self.assertEqual(label.text(), '')
        # 2) The component value should be updated to match the input
        self.assertCountEqual(component.value()[component.key], [{}])
        # 3) The component should not be declared valid -- because required arguments are not provided
        self.assertFalse(component.validate())
        # 4) The label text should not remain empty -- it should give a warning about the required fields
        for label in labels:
            self.assertNotEqual(label.text(), '')

        # Test inputting JSON data defined in "helpers.py" and updating the component.
        # There are two positioning stacks and four positioners
        json_data = json.loads(SAMPLE_IDF)

        # This should select the first positioning stack
        component.updateValue(json_data, '')
        stack_positioners = ['Positioning Table']
        leftover_positioners = ['Huber Circle', 'incident_jaws', 'diffracted_jaws', component.add_new_text]
        box_items = []
        combobox_items = []
        # 1) The fields in the component should be updated to match the expected result
        self.assertEqual(component.name_combobox.currentText(), 'Positioning Table Only')
        self.assertEqual(component.positioners_combobox.currentText(), 'Huber Circle')
        for index in range(component.positioners_combobox.count()):
            combobox_items.append(component.positioners_combobox.itemText(index))
        for index in range(component.positioning_stack_box.count()):
            box_items.append(component.positioning_stack_box.item(index).text())
        self.assertCountEqual(combobox_items, leftover_positioners)
        self.assertCountEqual(box_items, stack_positioners)
        # 2) The component value should be updated to match the input
        self.assertCountEqual(component.value()[component.key], json_data['instrument'][component.key])
        # 3) The component should be declared valid -- all required arguments are specified
        self.assertTrue(component.validate())
        # 4) The label text should remain empty -- as the component is valid
        for label in labels:
            self.assertEqual(label.text(), '')

        # If we switch positioning stack, this should be recorded in the component
        component.name_combobox.setCurrentIndex(1)
        component.name_combobox.activated.emit(1)
        stack_positioners = ['Positioning Table', 'Huber Circle']
        leftover_positioners = ['incident_jaws', 'diffracted_jaws', component.add_new_text]
        box_items = []
        combobox_items = []
        # 1) The fields in the component should be updated to match the expected result
        self.assertEqual(component.name_combobox.currentText(), 'Positioning Table + Huber Circle')
        self.assertEqual(component.positioners_combobox.currentText(), 'incident_jaws')
        for index in range(component.positioners_combobox.count()):
            combobox_items.append(component.positioners_combobox.itemText(index))
        for index in range(component.positioning_stack_box.count()):
            box_items.append(component.positioning_stack_box.item(index).text())
        self.assertCountEqual(box_items, stack_positioners)
        self.assertCountEqual(combobox_items, leftover_positioners)

        # If we use the "Add" button to add a positioner to the stack, this should be recorded in the component
        component.add_button.clicked.emit(1)
        stack_positioners = ['Positioning Table', 'Huber Circle', 'incident_jaws']
        leftover_positioners = ['diffracted_jaws', component.add_new_text]
        box_items = []
        combobox_items = []
        # 1) The fields in the component should be updated to match the expected result
        self.assertEqual(component.name_combobox.currentText(), 'Positioning Table + Huber Circle')
        self.assertEqual(component.positioners_combobox.currentText(), 'diffracted_jaws')
        for index in range(component.positioners_combobox.count()):
            combobox_items.append(component.positioners_combobox.itemText(index))
        for index in range(component.positioning_stack_box.count()):
            box_items.append(component.positioning_stack_box.item(index).text())
        self.assertCountEqual(box_items, stack_positioners)
        self.assertCountEqual(combobox_items, leftover_positioners)

        # If we use the "Add" button to add a new positioner to the stack, this should be recorded in the component
        new_positioner = 'New Positioner'
        component.positioners_combobox.setCurrentIndex(1)
        component.positioners_combobox.setCurrentText(new_positioner)
        component.add_button.clicked.emit(1)
        stack_positioners = ['Positioning Table', 'Huber Circle', 'incident_jaws', new_positioner]
        leftover_positioners = ['diffracted_jaws', component.add_new_text]
        box_items = []
        combobox_items = []
        # 1) The fields in the component should be updated to match the expected result
        self.assertEqual(component.name_combobox.currentText(), 'Positioning Table + Huber Circle')
        self.assertEqual(component.positioners_combobox.currentText(), '')
        for index in range(component.positioners_combobox.count()):
            combobox_items.append(component.positioners_combobox.itemText(index))
        for index in range(component.positioning_stack_box.count()):
            box_items.append(component.positioning_stack_box.item(index).text())
        self.assertCountEqual(box_items, stack_positioners)
        self.assertCountEqual(combobox_items, leftover_positioners)

        # If we use the "Add" button to add an existing positioner to the stack,
        # the positioner should move to the end of the list
        component.positioners_combobox.setCurrentIndex(1)
        component.positioners_combobox.setCurrentText('Huber Circle')
        component.add_button.clicked.emit(1)
        stack_positioners = ['Positioning Table', 'incident_jaws', new_positioner, 'Huber Circle']
        leftover_positioners = ['diffracted_jaws', component.add_new_text]
        box_items = []
        combobox_items = []
        # 1) The fields in the component should be updated to match the expected result
        self.assertEqual(component.name_combobox.currentText(), 'Positioning Table + Huber Circle')
        self.assertEqual(component.positioners_combobox.currentText(), '')
        for index in range(component.positioners_combobox.count()):
            combobox_items.append(component.positioners_combobox.itemText(index))
        for index in range(component.positioning_stack_box.count()):
            box_items.append(component.positioning_stack_box.item(index).text())
        self.assertCountEqual(box_items, stack_positioners)
        self.assertCountEqual(combobox_items, leftover_positioners)

        # If we use the "Clear" button to remove positioners from the stack, this should be recorded in the component
        # but undefined positioners should not appear in the combobox
        component.clear_button.clicked.emit(1)
        stack_positioners = []
        leftover_positioners = [
            'Positioning Table', 'Huber Circle', 'incident_jaws', 'diffracted_jaws', component.add_new_text
        ]
        box_items = []
        combobox_items = []
        # 1) The fields in the component should be updated to match the expected result
        self.assertEqual(component.name_combobox.currentText(), 'Positioning Table + Huber Circle')
        self.assertEqual(component.positioners_combobox.currentText(), 'Positioning Table')
        for index in range(component.positioners_combobox.count()):
            combobox_items.append(component.positioners_combobox.itemText(index))
        for index in range(component.positioning_stack_box.count()):
            box_items.append(component.positioning_stack_box.item(index).text())
        self.assertCountEqual(box_items, stack_positioners)
        self.assertCountEqual(combobox_items, leftover_positioners)

        # If we switch to the "Add New..." options, text fields should be cleared
        component.name_combobox.setCurrentIndex(2)
        component.name_combobox.activated.emit(1)
        # 1) The fields in the component should be cleared
        self.assertEqual(component.name_combobox.currentText(), '')
        self.assertEqual(component.positioners_combobox.currentText(), 'Positioning Table')
        self.assertEqual(component.positioning_stack_box.count(), 0)
        for label in labels:
            self.assertEqual(label.text(), '')
        # 2) The component should not be declared valid -- because required arguments are not provided
        self.assertFalse(component.validate())
        # 3) The label text should not remain empty -- it should give a warning about the required fields
        for label in labels:
            self.assertNotEqual(label.text(), '')
        # 4) When adding a new positioner, the positioners combobox should be cleared
        component.positioners_combobox.setCurrentIndex(4)
        component.positioners_combobox.activated.emit(1)
        self.assertEqual(component.positioners_combobox.currentText(), '')

        # Add new positioning stack
        component.name_combobox.setCurrentText('New stack')
        json_data['instrument'].update(component.value())
        component.updateValue(json_data, '')
        # 4) When adding the hardware, it should appear in the JSON
        stacks = json_data.get('instrument').get('positioning_stacks')
        new_stacks = ['Positioning Table Only', 'Positioning Table + Huber Circle', 'New stack']
        for index, stack in enumerate(stacks):
            self.assertEqual(stack['name'], new_stacks[index])
