from PyQt5 import QtCore, QtWidgets
from functools import partial
from sscanss.core.instrument.robotics import Link
import json
import sscanss.editor.json_attributes as im


class ObjectStack(QtWidgets.QWidget):
    """Holds the stack of selected objects to allow the user navigate the Json file and edit nested objects
    :param parent: parent widget
    :type parent: QWidget
    """
    stackChanged = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self.layout = QtWidgets.QHBoxLayout(self)
        self.setLayout(self.layout)
        self.object_stack = []
        self.stackChanged.connect(self.createUi)

    def clearLayout(self):
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().setParent(None)

    def createUi(self):
        """Recreates the UI based on the contents of the stack, creating a button for each object
        there to allow the user to return to any of the previous objects
        """
        self.clearLayout()
        first = True
        for title, object in self.object_stack:
            if first:
                first = False
            else:
                label = QtWidgets.QLabel(">")
                label.setMaximumSize(10, 50)
                self.layout.addWidget(label)

            button = QtWidgets.QPushButton(title)
            button.clicked.connect(partial(self.goDown, object))
            button.setMaximumSize(100, 50)
            self.layout.addWidget(button, 0, QtCore.Qt.AlignLeft)

    def addObject(self, object_title, new_object):
        """Adds another object on top of the stack and updates UI accordingly
        :param object_title: title of the object to be shown in the button
        :type object_title: str
        :param new_object: the object to be added
        :type new_object: JsonObjectAttribute
        """
        self.object_stack.append((object_title, new_object))
        self.stackChanged.emit()

    def goDown(self, selected_object):
        """Goes down the stack removing all objects until the selected one
        :param selected_object: Object on top of which everything will be removed
        :type selected_object: JsonObjectAttribute
        """
        while self.top() != selected_object:
            self.object_stack.pop(-1)

        self.stackChanged.emit()

    def top(self):
        """Returns the stack on top of the stack - it is supposed to be currently active
        :return selected_object: the top object
        :rtype selected_object: JsonObjectAttribute
        """
        title, obj = self.object_stack[-1]
        return obj


class Designer(QtWidgets.QWidget):
    data_changed = QtCore.pyqtSignal(str)

    def __init__(self, parent):
        """Creates an instance of the designer widget to edit a Json file with a GUI
        :param parent: instance of the main window
        :type parent: MainWindow
        """
        super().__init__(parent)

        self.object_stack = ObjectStack(self)
        self.object_stack.stackChanged.connect(self.createUi)

        self.attributes_panel = QtWidgets.QWidget(self)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(self.layout)
        self.layout.addWidget(self.object_stack)
        self.layout.addWidget(self.attributes_panel)

        self.instrument = self.createSchema()
        self.instrument.been_set.connect(self.DataChanged)

        self.object_stack.addObject("instrument", self.instrument)

    def DataChanged(self):
        self.data_changed.emit(self.getJsonFile())

    def createAttributeArray(self, attribute, number, custom_title="", mandatory=False):
        return im.ValueArray([attribute.defaultCopy() for i in range(number)], custom_title=custom_title,
                             mandatory=mandatory)

    def createVisualObject(self, mandatory=True):
        visual_attr = {"pose": self.createAttributeArray(im.FloatValue(), 6, mandatory=False),
                       "colour": im.ColourValue(mandatory=False),
                       "mesh": im.FileValue('', '')}

        visual_object = im.DirectlyEditableObject(visual_attr, self.object_stack, mandatory=mandatory,
                                                  custom_title="Model")
        return visual_object

    def createSchema(self):
        key = "name"
        fixed_hardware_attr = {key: im.StringValue("Fixed Hardware"),
                               "visual": self.createVisualObject()}
        fixed_hardware_arr = im.ObjectArray([im.JsonObject(fixed_hardware_attr,
                                                           self.object_stack)], key, self.object_stack, mandatory=False)

        link_attr = {key: im.StringValue("Link"),
                     "visual": self.createVisualObject(mandatory=False)}
        link_arr = im.ObjectArray([im.JsonObject(link_attr, self.object_stack)], key, self.object_stack)

        joint_attr = {key: im.StringValue("Joint"),
                      "type": im.EnumValue(Link.Type),
                      "parent": im.JsonObjectReference("././links"),
                      "child": im.JsonObjectReference("././links"),
                      "axis": self.createAttributeArray(im.FloatValue(), 3),
                      "origin": self.createAttributeArray(im.FloatValue(), 3),
                      "lower_limit": im.FloatValue(custom_title="Min offset"),
                      "upper_limit": im.FloatValue(custom_title="Max offset"),
                      "home_offset": im.FloatValue(mandatory=False)}
        joint_arr = im.ObjectArray([im.JsonObject(joint_attr, self.object_stack)], key, self.object_stack)

        positioner_attr = {key: im.StringValue("Positioner"),
                           "base": self.createAttributeArray(im.FloatValue(), 6, mandatory=False),
                           "tool": self.createAttributeArray(im.FloatValue(), 6, mandatory=False),
                           "custom_order": im.ObjectOrder("joints", mandatory=False),
                           "joints": joint_arr,
                           "links": link_arr}

        positioner_arr = im.ObjectArray([im.JsonObject(positioner_attr, self.object_stack)], key, self.object_stack)

        jaws_attr = {"aperture": self.createAttributeArray(im.FloatValue(), 2),
                     "aperture_lower_limit": self.createAttributeArray(im.FloatValue(), 2),
                     "aperture_upper_limit": self.createAttributeArray(im.FloatValue(), 2),
                     "beam_direction": self.createAttributeArray(im.FloatValue(), 3),
                     "beam_source": self.createAttributeArray(im.FloatValue(), 3),
                     "positioner": im.JsonObjectReference("./positioners", mandatory=False),
                     "visual": self.createVisualObject()}
        jaws_object = im.JsonObject(jaws_attr, self.object_stack)

        collimator_attr = {key: im.StringValue("Collimator"),
                           "aperture": self.createAttributeArray(im.FloatValue(), 2),
                           "visual": self.createVisualObject()}
        collimator_arr = im.ObjectArray([im.JsonObject(collimator_attr, self.object_stack)],
                                        key, self.object_stack, mandatory=False)

        detector_attr = {key: im.StringValue("Detector"),
                         "collimators": collimator_arr,
                         "default_collimator": im.JsonObjectReference("collimators", mandatory=False),
                         "diffracted_beam": self.createAttributeArray(im.FloatValue(), 3),
                         "positioner": im.JsonObjectReference("././positioners", mandatory=False)}
        detector_arr = im.ObjectArray([im.JsonObject(detector_attr, self.object_stack)],
                                      key, self.object_stack)

        positioning_stack_attr = {key: im.StringValue("Positioning stack"),
                                  "positioners": im.ObjectOrder("././positioners")}

        positioning_stack_arr = im.ObjectArray([im.JsonObject(positioning_stack_attr, self.object_stack)], key,
                                               self.object_stack)

        instrument_attr = {"name": im.StringValue("Instrument"),
                           "version": im.StringValue(),
                           "script_template": im.FileValue('', mandatory=False),
                           "gauge_volume": self.createAttributeArray(im.FloatValue(), 3),
                           "incident_jaws": jaws_object,
                           "detectors": detector_arr,
                           "positioning_stacks": positioning_stack_arr,
                           "positioners": positioner_arr,
                           "fixed_hardware": fixed_hardware_arr}

        instrument_obj = im.JsonObject(instrument_attr, self.object_stack)

        return instrument_obj

    def getJsonFile(self):
        """Returns dictionary, representing a json object created from the data in the designer
        :return: the json dictionary
        :rtype: dict{str: object}
        """
        json_dict = self.instrument.json_value
        json_dict["collimators"] = []
        for detector in json_dict["detectors"]:
            for collimator in detector["collimators"]:
                collimator["detector"] = detector["name"]
                json_dict["collimators"].append(collimator)
            del detector["collimators"]

        return json.dumps({"instrument": json_dict})

    def setJsonFile(self, text):
        """Loads the text representing json file into the schema to set the relevant data
        :param text: the json file text
        :type text: str
        """
        # Here also change the json schema by moving collimators into the detector objects
        instrument_dict = json.loads(text)["instrument"]

        for detector in instrument_dict["detectors"]:
            detector["collimators"] = [{key: value for key, value in collimator.items() if key != "detector"}
                                       for collimator in instrument_dict["collimators"] if collimator["detector"] ==
                                       detector["name"]]
        del instrument_dict["collimators"]

        self.instrument.json_value = instrument_dict
        self.createUi()

    def createUi(self):
        """Updates the UI according to the top object in the stack"""
        self.attributes_panel.setParent(None)
        self.attributes_panel = self.object_stack.top().createPanel()
        self.layout.addWidget(self.attributes_panel)
