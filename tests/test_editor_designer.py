import unittest
from unittest import mock
from PyQt5 import QtCore, QtWidgets, QtGui
import sscanss.editor.json_attributes as im
import sscanss.editor.designer as d
from sscanss.core.util.widgets import FilePicker, ColourPicker
from enum import Enum
from helpers import APP, TestSignal


class TestEnum(Enum):
    ZERO = "Zero"
    ONE = "One"
    TWO = "Two"
    THREE = "Three"


class TestDesignerTree(unittest.TestCase):
    def testStringAttribute(self):
        string_attr = im.StringValue()

        self.assertEqual(string_attr.value, '')
        test_string = "This is a string"
        string_attr = im.StringValue(test_string)
        m = mock.Mock()
        string_attr.been_set.connect(m)
        self.assertEqual(string_attr.value, test_string)
        new_string = "New string"
        string_attr.setValue(new_string)
        self.assertEqual(string_attr.value, new_string)
        control_widget = string_attr.createEditWidget()
        self.assertIsInstance(control_widget, QtWidgets.QLineEdit)
        self.assertEqual(control_widget.text(), new_string)
        self.assertEqual(string_attr.json_value, new_string)
        m.assert_called_with(new_string)
        json_string = "Json string"
        string_attr.json_value = json_string
        self.assertEqual(string_attr.value, json_string)

        copy_string = string_attr.defaultCopy()
        self.assertEqual(copy_string.value, '')
        self.assertIsInstance(copy_string, im.StringValue)

    def testFloatAttribute(self):
        float_attr = im.FloatValue()

        self.assertEqual(float_attr.value, 0.0)
        test_float = 5.0
        float_attr = im.FloatValue(test_float)
        m = mock.Mock()
        float_attr.been_set.connect(m)
        self.assertEqual(float_attr.value, test_float)
        new_float = 7.32
        float_attr.setValue(new_float)
        self.assertEqual(float_attr.value, new_float)
        control_widget = float_attr.createEditWidget()
        self.assertIsInstance(control_widget, QtWidgets.QDoubleSpinBox)
        self.assertEqual(control_widget.value(), new_float)
        self.assertEqual(float_attr.json_value, new_float)
        m.assert_called_with(new_float)
        json_float = -1.53
        float_attr.json_value = json_float
        self.assertEqual(float_attr.value, json_float)
        m.assert_called_with(new_float)

        copy_float = float_attr.defaultCopy()
        self.assertEqual(copy_float.value, 0.0)
        self.assertIsInstance(copy_float, im.FloatValue)

    def testAttributeArray(self):
        string_val = "String"
        float_val = -53.2
        int_val = 423

        m1 = mock.Mock()
        m1.createWidget = mock.Mock(return_value=QtWidgets.QLineEdit())
        m1.been_set = TestSignal()
        m1.value = string_val
        m2 = mock.MagicMock()
        m2.createWidget = mock.Mock(return_value=QtWidgets.QDoubleSpinBox())
        m2.been_set = TestSignal()
        m2.value = float_val
        m3 = mock.MagicMock()
        m3.createWidget = mock.Mock(return_value=QtWidgets.QLabel())
        m3.been_set = TestSignal()
        m3.value = int_val
        array_attribute = im.ValueArray([m1, m2, m3])
        mock_event_handler = mock.Mock()
        array_attribute.been_set.connect(mock_event_handler)
        self.assertListEqual(array_attribute.values, [m1, m2, m3])
        widget = array_attribute.createEditWidget()
        self.assertEqual(widget.layout.count(), 3)
        self.assertListEqual(array_attribute.value, [string_val, float_val, int_val])
        mock_event_handler.assert_not_called()
        m1.been_set.emit("New")
        m2.been_set.emit(976.3)
        m3.been_set.emit(-53)
        self.assertEqual(mock_event_handler.call_count, 3)
        self.assertListEqual(mock_event_handler.call_args_list, [mock.call("New"), mock.call(976.3), mock.call(-53)])

    def testEnumAttribute(self):
        enum_attr = im.EnumValue(TestEnum)

        self.assertEqual(enum_attr.value, 0)
        test_index = 1
        enum_attr = im.EnumValue(TestEnum, test_index)
        m = mock.Mock()
        enum_attr.been_set.connect(m)
        self.assertEqual(enum_attr.value, test_index)
        new_index = 0
        enum_attr.setValue(0)
        self.assertEqual(enum_attr.value, new_index)
        control_widget = enum_attr.createEditWidget()
        self.assertIsInstance(control_widget, QtWidgets.QComboBox)
        self.assertEqual(control_widget.currentIndex(), new_index)
        self.assertEqual(enum_attr.json_value, "Zero")
        m.assert_called_with(new_index)
        json_value = "Three"
        enum_attr.json_value = json_value
        self.assertEqual(enum_attr.value, 3)
        m.assert_called_with(new_index)

        copy_enum = enum_attr.defaultCopy()
        self.assertEqual(copy_enum.value, 0.0)
        self.assertIsInstance(copy_enum, im.EnumValue)

    def testColourAttribute(self):

        colour_attr = im.ColourValue()
        self.assertEqual(colour_attr.value, QtGui.QColor())
        test_colour = QtGui.QColor(53, 12, 154)
        colour_attr = im.ColourValue(test_colour)
        event_handler = mock.Mock()
        colour_attr.been_set.connect(event_handler)
        self.assertEqual(colour_attr.value, test_colour)
        new_colour = QtGui.QColor(43, 11, 211)
        colour_attr.setValue(new_colour)
        self.assertEqual(colour_attr.value, new_colour)
        control_widget = colour_attr.createEditWidget()
        self.assertIsInstance(control_widget, ColourPicker)
        self.assertEqual(control_widget.value, new_colour)

        rgb_size = 255

        self.assertEqual(colour_attr.json_value, [new_colour.redF()/rgb_size, new_colour.greenF()/rgb_size,
                                                  new_colour.blueF()/rgb_size])
        json_colour = [0.4, 0.8, 0.06]
        colour_attr.json_value = json_colour
        actual_json_colour = QtGui.QColor(int(json_colour[0]*rgb_size), int(json_colour[1]*rgb_size),
                                          int(json_colour[2]*rgb_size))
        self.assertEqual(colour_attr.value, actual_json_colour)
        event_handler.assert_called_with(new_colour)

        copy_colour = colour_attr.defaultCopy()
        self.assertEqual(copy_colour.value, QtGui.QColor())
        self.assertIsInstance(copy_colour, im.ColourValue)

    def testObjectReferenceAttribute(self):
        mock_parent = mock.Mock()
        mock_child1 = mock.Mock()
        mock_child1.tree_parent = mock_parent
        mock_child2 = mock.Mock()
        mock_child2.tree_parent = mock_parent
        key_list = ["key1", "key2", "key3"]
        mock_child2.getObjectKeys = mock.Mock(return_value=key_list)
        mock_child2.objects = mock.MagicMock()
        mock_parent.attributes = {"child": mock_child2}

        reference_attr = im.JsonObjectReference("./child")
        reference_attr.tree_parent = mock_child1
        event_handler = mock.MagicMock()
        reference_attr.been_set = event_handler
        self.assertEqual(reference_attr.object_array, mock_child2)
        widget = reference_attr.createEditWidget()
        self.assertIsInstance(widget, QtWidgets.QComboBox)
        self.assertEqual(reference_attr.value, key_list[0])
        self.assertEqual(widget.currentIndex(), 0)
        self.assertListEqual([widget.itemText(i) for i in range(widget.count())], key_list)
        self.assertEqual(widget.currentText(), reference_attr.value)
        widget.setCurrentIndex(2)
        event_handler.assert_called_with(2)
        self.assertEqual(widget.currentText(), "key2")
        self.assertEqual(reference_attr.value, "key2")

        copy_ref = reference_attr.defaultCopy()
        mock_parent_copy = mock.Mock()
        mock_child1_copy = mock.Mock()
        mock_child1_copy.tree_parent = mock_parent_copy
        mock_child2_copy = mock.Mock()
        mock_child2_copy.tree_parent = mock_parent_copy
        mock_child2_copy.getObjectKeys = mock.Mock(return_value=key_list)
        mock_parent_copy.attributes = {"child": mock_child2_copy}

        copy_ref.tree_parent = mock_child1_copy
        self.assertIsInstance(copy_ref, im.JsonObjectReference)
        self.assertEqual(copy_ref.object_array, mock_child2_copy)

    def testObjectOrderAttribute(self):
        pass

    def testObjectList(self):
        pass

    def testObject(self):
        pass

    def testDirectlyEditableObject(self):
        pass

class TestDesignerWidget(unittest.TestCase):
    def testObjectStack(self):
        stack = d.ObjectStack(None)
        event_handler = mock.Mock()
        stack.stackChanged.connect(event_handler)
        event_handler.assert_not_called()
        obj1 = mock.Mock()
        obj2 = mock.Mock()
        obj3 = mock.Mock()
        obj4 = mock.Mock()
        stack.addObject(obj1, "First")
        self.assertEqual(event_handler.call_count, 1)
        self.assertEqual(stack.top(), obj1)
        stack.addObject(obj2, "Second")
        stack.addObject(obj3, "Third")
        self.assertEqual(stack.top(), obj3)
        self.assertEqual(event_handler.call_count, 3)
        stack.goDown(obj2)
        self.assertEqual(stack.top(), obj2)
        self.assertEqual(event_handler.call_count, 4)
        stack.addObject(obj4)
        self.assertEqual(stack.top(), obj4)

    def testDesigner(self):
        pass
