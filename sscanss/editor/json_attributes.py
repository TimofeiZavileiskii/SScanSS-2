from functools import partial
import os
from PyQt5 import QtWidgets, QtCore, QtGui
from sscanss.core.util.widgets import FilePicker, ColourPicker


class RelativeReference:
    def __init__(self, path_to_list):
        """Object implements algorithm to find the required object in the tree
        :param path_to_list: represents the path to the needed list starting from the parent object of the attribute:
         - movements are separated by '/', '.' represents going to previous object
         - anything else is name of object attribute to go into
        :type path_to_list: str
        """
        self.path_to_list = path_to_list

    def getRelativeReference(self, caller):
        """Method to find the list based on the address
        :param caller: the attribute which has the path
        :type caller: ListReference
        :return: the list in the given address
        :rtype: ObjectList
        """
        commands = self.path_to_list.split('/')
        current_object = caller.parent
        for command in commands:
            if command == ".":
                current_object = current_object.parent
            else:
                current_object = current_object.value[command]
        return current_object


class JsonAttributes:
    def __init__(self):
        """The collection of the json object attributes"""
        self.attributes = {}

    @staticmethod
    def formatTitle(key):
        """Formats key into a title by splitting words on '_' and capitalising first letters
        :pram key: the string to be formatted
        :type key: str
        :return: the title obtained from the key
        :rtype: str
        """
        return ' '.join([word.capitalize() for word in key.split('_')])

    def addAttribute(self, key, json_value, title=None, mandatory=True):
        """Adds attribute to the list based on the given parameters
        :param key: the unique key of the attribute to identity it
        :type key: str
        :param json_value: the value object which manages the actual value of the attribute
        :type json_value: JsonValue
        :param title: the title of the attribute to be used in UI, by default is generated from key
        :type title: str
        :param mandatory: whether the attribute is mandatory and can be switched off
        :type mandatory: bool
        """
        if not title:
            title = self.formatTitle(key)

        self.attributes[key] = JsonAttribute(json_value, title, mandatory)

    def defaultCopy(self):
        """The same as for json_value - generates a copy of itself with the same attributes
        :return: the copy of the attributes
        :rtype: JsonAttributes
        """
        copy = JsonAttributes()
        for key, attribute in self.attributes.items():
            copy.attributes[key] = attribute.defaultCopy()

        return copy

    def __getitem__(self, key):
        """Gets the value from the json value object at the given key
        :return: the value of the selected attribute
        :rtype: object
        """
        return self.attributes[key].value

    def __iter__(self):
        """iterated over the list by outputting the attributes keys and values
        :return: the key value pair from the dictionary of attributes
        :rtype: str, JsonAttribute
        """
        for key, attribute in self.attributes.items():
            yield key, attribute


class JsonAttribute(QtCore.QObject):
    been_set = QtCore.pyqtSignal(object)

    def __init__(self, json_value, title, mandatory):
        """The contained for the attribute value
        :param json_value: the value object to manage the contained value
        :type json_value: JsonValue
        :param title: the title of the attribute to be used in the UI
        :type title: str
        :param mandatory: whether the attribute is mandatory and can be disabled
        :type mandatory: bool
        """
        super().__init__()
        self.value = json_value
        self.value.been_set.connect(self.been_set.emit)
        self.title = title
        self.mandatory = mandatory
        self.turned_on = True

    def setTurnedOn(self, new_state):
        self.turned_on = new_state
        self.been_set.emit(self.turned_on)

    def defaultCopy(self):
        """Copies itself with the same value type and other parameters
        :return: the copy of the attribute
        :rtype: JsonAttribute
        """
        return JsonAttribute(self.value.defaultCopy(), self.title, self.mandatory)

    def resolveReferences(self):
        """Resolves the reference for the attribute value, important only if the value is of type ListReference"""
        self.value.resolveReferences()

    def createWidget(self):
        """Creates a widget which contains the title label, widget to edit the value and a checkbox to disable
         the attribute if it is not mandatory
        :return: the attribute's widget
        :rtype: QWidget
        """
        widget = QtWidgets.QWidget()
        widget.layout = QtWidgets.QHBoxLayout()
        widget.setLayout(widget.layout)

        label = QtWidgets.QLabel(self.title)
        widget.layout.addWidget(label)
        edit_widget = self.value.createEditWidget(self.title)
        widget.layout.addWidget(edit_widget)

        if not self.mandatory:
            checkbox = QtWidgets.QCheckBox("Include")
            checkbox.setChecked(self.turned_on)
            checkbox.stateChanged.connect(self.setTurnedOn)
            widget.layout.addWidget(checkbox)

        return widget

    def connectParent(self, parent):
        """Connects the parent for the value inside
        :param parent: the parent to connect to the value
        :type parent: JsonValue
        """
        self.value.connectParent(parent)

    @property
    def json_value(self):
        """Returns the json value of itself"""
        return self.value.json_value

    @json_value.setter
    def json_value(self, value):
        """Sets the value from the json representation"""
        self.value.json_value = value


class JsonValue(QtCore.QObject):
    been_set = QtCore.pyqtSignal(object)
    default_value = None

    def __init__(self, initial_value=None):
        """The parent class of all the nodes in the tree
        Contains the methods which should be overridden by the child classes
        :param initial_value: the initial value of the object, if left empty will be overwritten by the default value
        :type initial_value: object
        """
        super().__init__()
        self.parent = False
        if initial_value:
            self.value = initial_value
        else:
            self.value = self.default_value

    def createEditWidget(self, title=''):
        """Creates the widget which should be used in the UI to edit the data.
        It is linked with the object using events
        :param title: title the which should be used inside the widget if it is needed
        :type title: str
        """
        return QtWidgets.QWidget()

    def defaultCopy(self):
        """Creates a copy of the attribute, it is needed to be able to create an object,
        following the same schema as another object
        :return: the copy of self, following the same schema
        :rtype: JsonValue
        """
        return type(self)()

    def connectParent(self, parent):
        """Connects self to the parent node in the tree needed to be able to backtrack the tree and send the
        events up the tree
        :param parent: the parent of the node
        :type parent: JsonValue
        """
        self.been_set.connect(parent.been_set.emit)
        self.parent = parent

    def resolveReferences(self):
        """The method should either resolve references for the list references or propagate the call down the tree.
        If irrelevant should be left empty.
        """
        pass

    def setValue(self, new_value):
        """Sets the value and calls the event about the change. Should be used as the event handler to connect to
        the widget
        :param new_value: the new value to be set
        :type new_value: object
        """
        self.value = new_value
        self.been_set.emit(new_value)

    @property
    def json_value(self):
        """Returns the value from the attribute, suitable for use in a Json file"""
        return self.value

    @json_value.setter
    def json_value(self, value):
        """Sets the value in the attribute from the value passed from a Json file"""
        self.value = value


class StringValue(JsonValue):
    """Value which contains a string"""
    default_value = ''

    def createEditWidget(self, title=''):
        """Creates a line edit to modify the string in the attribute
        :return: the line edit
        :rtype: QLineEdit
        """
        widget = QtWidgets.QLineEdit(self.value)
        widget.textEdited.connect(self.setValue)
        return widget


class FileValue(JsonValue):
    default_value = ''

    def __init__(self, directory='', filter='', initial_value=None):
        """Attribute which should allow to modify a file path
        :param directory: the initial directory which will be suggested to a user
        :type directory: str
        :param filter: which files should be allowed to be open
        :type filter: str
        :param value: the initial address in the attribute
        :type value: str
        """
        super().__init__(initial_value)
        self.directory = directory
        self.filter = filter

    def createEditWidget(self, title=''):
        """Creates the file picker to choose the filepath in the attribute
        :return: the file picker
        :rtype: FilePicker
        """
        widget = FilePicker(self.directory, False, self.filter)
        widget.value = self.value
        widget.value_changed.connect(self.setValue)

        return widget

    def defaultCopy(self):
        return type(self)(self.directory, self.filter)


class FloatValue(JsonValue):
    """Attribute manages the float values in objects"""
    default_value = 0.0

    def createEditWidget(self, title=''):
        """Creates a spin box to enter a float value
        :return: The spin box
        :rtype: QDoubleSpinBox
        """
        widget = QtWidgets.QDoubleSpinBox()
        widget.setRange(float("-inf"), float("inf"))
        widget.setValue(self.value)
        widget.valueChanged.connect(self.setValue)
        return widget


class ValueArray(JsonValue):
    default_value = []

    def __init__(self, values):
        """Array of several attributes allowing to edit them on the same line
        :param values: the list of attribute values to be used in the value array
        :type values:
        """
        super().__init__(values)

        for individual_value in self.value:
            individual_value.been_set.connect(self.been_set.emit)

    def createEditWidget(self, title=''):
        """Creates a widget which itself contains widgets of the attributes
        :return: the widget with attributes' widgets to be displayed
        :rtype: QWidget
        """
        array_widget = QtWidgets.QWidget()
        array_widget.layout = QtWidgets.QHBoxLayout()
        array_widget.setLayout(array_widget.layout)

        for attribute in self.value:
            array_widget.layout.addWidget(attribute.createEditWidget())

        array_widget.layout.setContentsMargins(0, 0, 0, 0)

        return array_widget

    def connectParent(self, parent):
        for individual_value in self.value:
            individual_value.connectParent(parent)

    def resolveReferences(self):
        for individual_value in self.value:
            individual_value.resolveReferences()

    def defaultCopy(self):
        return type(self)([individual_value.defaultCopy() for individual_value in self.value])

    @property
    def json_value(self):
        return [individual_value.json_value for individual_value in self.value]

    @json_value.setter
    def json_value(self, value):
        for i, new_json_value in enumerate(value):
            self.value[i].json_value = new_json_value


class ColourValue(JsonValue):
    """Attribute which manages attribute responsible for colour. The colour is in normalised form
    """
    rgbSize = 255
    default_value = [0.0, 0.0, 0.0]

    def createEditWidget(self, title=''):
        """Creates a custom picker widget which allows user to pick a colour and then displays it
        :return: the colour picker
        :rtype: ColourPicker
        """
        widget = ColourPicker(QtGui.QColor(int(self.value[0] * self.rgbSize), int(self.value[1] * self.rgbSize),
                              int(self.value[2] * self.rgbSize)))
        widget.value_changed.connect(self.setValue)
        return widget

    def setValue(self, new_value):
        """Sets the new colour value in the object
        :param new_value: the new value
        :type new_value: list
        """
        super().setValue([new_value[0], new_value[1], new_value[2]])


class EnumValue(JsonValue):
    """Attribute which allows to select a value from an enum
    :param enum_class: the class to chose value from
    :type enum_class: Enum
    :param value: the initial selected index
    :type value: int
    """
    default_value = 0

    def __init__(self, enum_class, initial_value=None):
        super().__init__(initial_value)
        self.enum = enum_class
        self.enum_list = [option.value for option in self.enum]

    def createEditWidget(self, title=''):
        """Creates combobox with the options as all possible values of the enum
        :return: the combo box to edit enum values
        :rtype: QComboBox
        """
        widget = QtWidgets.QComboBox()
        widget.addItems(self.enum_list)
        widget.setCurrentIndex(self.value)
        widget.currentIndexChanged.connect(self.setValue)

        return widget

    def defaultCopy(self):
        return type(self)(self.enum)

    @property
    def json_value(self):
        return self.enum_list[self.value]

    @json_value.setter
    def json_value(self, value):
        self.value = self.enum_list.index(value)


class ListReference(JsonValue):
    def __init__(self, list_path, initial_value=None):
        """Attribute which depends on an external list
        :param list_path: the path in the tree to the object
        :type list_path: RelativeReference
        :param initial_value: the initial value of the selected object
        :type initial_value: str
        """
        super().__init__(initial_value)
        self.list_path = list_path
        self._list_reference = None

    @property
    def list_reference(self):
        return self._list_reference

    @list_reference.setter
    def list_reference(self, value):
        if value is None:
            print("Error")

        self._list_reference = value

    def updateOnListChange(self):
        """The method should be overridden by the child classes. It should be called every time the value
        of the list is updated to adapt to changes made by the user when editing the referenced list"""
        pass

    def defaultCopy(self):
        return type(self)(self.list_path)

    def resolveReferences(self):
        """Gets the list given by the relative reference. It must be called after all nodes have been connected"""
        self.list_reference = self.list_path.getRelativeReference(self)
        self.list_reference.been_set.connect(self.updateOnListChange)


class SelectedObject(ListReference):
    """Attribute which contains name of an object from an object array"""
    default_value = ''

    def newIndex(self, new_index):
        """Updates the value when new index is selected
        :param new_index: the new index
        :type new_index: int
        """
        self.value = self.list_reference.getObjectKeys()[new_index]
        self.list_reference.value[new_index].been_set.connect(self.updateValue)

    def updateOnListChange(self):
        if self.value not in self.list_reference.getObjectKeys():
            self.newIndex(0)

    def updateValue(self, new_value):
        """Updates the value in the attribute without calling the been_set signal"""
        self.value = new_value

    def createEditWidget(self, title=''):
        """Creates a combobox to choose one object from already existing ones in the list
        :return: the combobox where the user can select the object
        :rtype: QComboBox
        """
        self.combo_box = QtWidgets.QComboBox()
        if not self.list_reference:
            print("ERROR")
        self.combo_box.addItems(self.list_reference.getObjectKeys())
        self.combo_box.currentIndexChanged.connect(self.newIndex)

        return self.combo_box


class DropList(QtWidgets.QListWidget):
    """The object is like the normal QList but fires an event when object is dragged and dropped"""
    itemDropped = QtCore.pyqtSignal()

    def dropEvent(self, event):
        super().dropEvent(event)
        self.itemDropped.emit()


class ObjectOrder(ListReference):
    """Attribute contains a custom order of objects in referenced list"""

    def itemDropped(self):
        """Should be called when an item is dragged and dropped to update the current value"""
        self.value = [self.obj_list.item(x).text() for x in range(self.obj_list.count())]

    def updateOnListChange(self):
        self.value = [item for item in self.value if item in self.list_reference.getObjectKeys()]
        self.value += [item for item in self.list_reference.getObjectKeys() if item not in self.value]

    def createEditWidget(self, title=''):
        """Creates a list which should allow to drag and drop items from the selected list
        :return: the list widget
        :rtype: DropList
        """
        if not self.value:
            self.value = self.list_reference.getObjectKeys()

        self.obj_list = DropList()
        self.obj_list.addItems(self.value)
        self.obj_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.obj_list.itemDropped.connect(self.itemDropped)

        return self.obj_list


class ObjectAttribute(JsonValue):
    def __init__(self, object_stack, initial_value=None):
        """Parent class of all the node attributes - classes should be able to be added to the object stack and
        allow to modify their attributes by getting their widgets
        :param object_stack: the reference to the object stack from the designer widget
        :type object_stack: ObjectStack
        """
        super().__init__(initial_value)
        self.object_stack = object_stack
        self.panel = None

    def createEditWidget(self, title=''):
        """Creates the button which would switch the UI of the designer to the current object by
        updating pushing itself on top of the object stack
        :return: The button liked to stack to push the object on top of it
        :rtype: QButton
        """
        button = QtWidgets.QPushButton("Edit " + title + "...")
        button.clicked.connect(partial(self.object_stack.addObject, title, self))
        return button

    def createPanel(self):
        """The panel is a widget which should display other attributes generated by the attributes
        of the object.
        :return: the panel widget
        :rtype: QWidget
        """
        return None


class JsonObject(ObjectAttribute):
    default_value = JsonAttributes()

    def __init__(self, object_stack, initial_value):
        """The json object which should manage the attributes
        :param object_stack: the reference of the object stack
        :type object_stack: ObjectStack
        :param initial_value: the attributes of the object
        :type initial_value: JsonAttributes
        """
        super().__init__(object_stack, initial_value)

        for key, attribute in self.value:
            attribute.connectParent(self)

    def createPanel(self):
        """Creates the panel widget by getting widgets from each attribute
        :return: the panel with other widgets
        :rtype: QWidget
        """
        attributes_panel = QtWidgets.QWidget()
        attributes_panel.layout = QtWidgets.QVBoxLayout()
        attributes_panel.setLayout(attributes_panel.layout)

        for attribute in self.value.attributes.values():
            attributes_panel.layout.addWidget(attribute.createWidget())

        return attributes_panel

    def resolveReferences(self):
        """Resolves the references to all the child attributes"""
        for key, attribute in self.value:
            attribute.resolveReferences()

    def defaultCopy(self):
        return type(self)(self.object_stack, self.value.defaultCopy())

    @property
    def json_value(self):
        return {key: attribute.json_value for key, attribute in self.value if self.value[key].turned_on}

    @json_value.setter
    def json_value(self, value):
        for key, attr_value in value.items():
            self.value[key].json_value = attr_value


class DirectlyEditableObject(JsonObject):
    """Class is the same as JsonObject but instead of creating button it allows to edit itself directly inside
    panel of owning object - object array
    """
    def createEditWidget(self, title=''):
        """Outputs instead of a button to select the object, a copy of the panel to directly edit the object among
        other attributes"""
        return self.createPanel()


class ObjectList(ObjectAttribute):
    def __init__(self, key, object_stack, initial_value):
        """The array of other objects which should allow the user to add, delete and edit each of them individually
           :param key: the name of the attribute which should be used to identify objects in the list
           :type key: str
           :param object_stack: the reference to the object stack from the designer widget
           :type object_stack: ObjectStack
           :param initial_value: the first object in the list to base other objects on it
           :type initial_value: JsonObject
            """
        super().__init__(object_stack, [initial_value])
        initial_value.connectParent(self)
        self.current_index = 0
        self.key_attribute = key

    def resolveReferences(self):
        """Resolves the references for the child objects"""
        for obj in self.value:
            obj.resolveReferences()

    @property
    def selected(self):
        return self.value[self.current_index]

    @selected.setter
    def selected(self, new_obj):
        self.value[self.current_index] = new_obj

    def comboboxNewSelected(self, new_index):
        """Should be triggered when user selects new value in the combobox
        :param new_index: the new index in the combobox
        :type new_index: int
        """
        self.current_index = new_index
        self.updateSelectedPanel()

    def updateSelectedPanel(self):
        """Updates the panel of the object currently selected in the combobox"""
        if self.panel.layout.itemAtPosition(1, 0):
            self.panel.layout.itemAtPosition(1, 0).widget().setParent(None)
        self.panel.layout.addWidget(self.selected.createPanel(), 1, 0)

    def updateComboBox(self):
        """Recreates the combobox when any information on it has changed"""
        combo_box = QtWidgets.QComboBox()
        combo_box.addItems(self.getObjectKeys())
        combo_box.setCurrentIndex(self.current_index)
        combo_box.currentIndexChanged.connect(self.comboboxNewSelected)

        if self.panel.layout.itemAtPosition(0, 0):
            self.panel.layout.itemAtPosition(0, 0).widget().setParent(None)

        self.panel.layout.addWidget(combo_box, 0, 0)

    def updateUi(self):
        """Updates the ui of the widget if it shown"""
        if self.panel:
            self.updateSelectedPanel()
            self.updateComboBox()

    def getObjectKeys(self):
        """
        The method returns the list with all the objects' keys
        :return: list of keys
        :rtype: list
        """
        return [obj.value[self.key_attribute].value for obj in self.value]

    def newObject(self):
        """Creates the new object in the end of the list and selects it"""
        new_object = self.value[0].defaultCopy()
        new_object.connectParent(self)
        self.value.append(new_object)
        self.current_index = len(self.value) - 1
        self.selected.value[self.key_attribute].been_set.connect(self.updateComboBox)
        self.updateUi()

    def deleteObject(self):
        """Deletes the current object, if it was the last remaining replaces it with a default copy"""
        if len(self.value) > 1:
            self.value.pop(self.current_index)
            if self.current_index > 0:
                self.current_index -= 1

            self.updateUi()

    def moveObject(self):
        """Moves the currently selected object by 1 in the list if it was not the last one"""
        moved_object = self.value.pop(self.current_index)
        if self.current_index < len(self.value):
            self.current_index += 1
        self.value.insert(self.current_index, moved_object)

        self.updateUi()

    def createPanel(self):
        """Creates the panel to be displayed with the combobox to select current object, button to add, delete and
        move objects, and the panel to edit the selected object
        :return: the panel widget
        :rtype: QWidget
        """
        self.panel = QtWidgets.QWidget()
        self.panel.layout = QtWidgets.QGridLayout()
        self.panel.setLayout(self.panel.layout)
        self.updateUi()

        self.buttons_widget = QtWidgets.QWidget()
        self.buttons_widget.layout = QtWidgets.QVBoxLayout()
        self.buttons_widget.setLayout(self.buttons_widget.layout)
        add_button = QtWidgets.QPushButton()
        add_button.setText("Add")
        add_button.clicked.connect(self.newObject)
        delete_button = QtWidgets.QPushButton()
        delete_button.setText("Delete")
        delete_button.clicked.connect(self.deleteObject)
        swap_button = QtWidgets.QPushButton()
        swap_button.setText("Swap")
        swap_button.clicked.connect(self.moveObject)
        self.buttons_widget.layout.addWidget(add_button)
        self.buttons_widget.layout.addWidget(delete_button)
        self.buttons_widget.layout.addWidget(swap_button)
        self.panel.layout.addWidget(self.buttons_widget, 0, 1, 2, 1)

        self.panel.layout.setRowStretch(3, 0)
        self.panel.layout.setRowStretch(3, 1)

        return self.panel

    def defaultCopy(self):
        return type(self)(self.key_attribute, self.object_stack, self.value[0].defaultCopy())

    @property
    def json_value(self):
        return [obj.json_value for obj in self.value]

    @json_value.setter
    def json_value(self, value):
        self.value = [self.value[0]]
        self.current_index = 0

        while len(self.value) < len(value):
            self.newObject()
            self.selected.json_value = value[self.current_index]

    def __iter__(self):
        for obj in self.value:
            yield obj
