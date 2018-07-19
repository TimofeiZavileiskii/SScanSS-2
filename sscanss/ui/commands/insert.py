from collections import OrderedDict
import logging
import os
import numpy as np
from PyQt5 import QtWidgets
from sscanss.core.util import Primitives, Worker
from sscanss.core.mesh import create_tube, create_sphere, create_cylinder, create_cuboid


class InsertPrimitive(QtWidgets.QUndoCommand):
    def __init__(self, primitive, args, presenter, combine):
        """ Command to insert primitive to the sample list

        :param primitive: primitive to insert
        :type primitive: sscanss.core.util.misc.Primitives
        :param args: arguments for primitive creation
        :type args: Dict
        :param presenter: Mainwindow presenter instance
        :type presenter: sscanss.ui.windows.main.presenter.MainWindowPresenter
        :param combine: when True primitive is added to current otherwise replaces it
        :type combine: bool
        """
        super().__init__()

        self.name = args.pop('name', 'unnamed')
        self.args = args
        self.primitive = primitive
        self.presenter = presenter
        self.combine = combine

        self.setText('Insert {}'.format(self.primitive.value))

    def redo(self):
        if not self.combine:
            self.old_sample = self.presenter.model.sample

        if self.primitive == Primitives.Tube:
            mesh = create_tube(**self.args)
        elif self.primitive == Primitives.Sphere:
            mesh = create_sphere(**self.args)
        elif self.primitive == Primitives.Cylinder:
            mesh = create_cylinder(**self.args)
        else:
            mesh = create_cuboid(**self.args)

        self.sample_key = self.presenter.model.addMeshToProject(self.name, mesh, combine=self.combine)

    def undo(self):
        if self.combine:
            self.presenter.model.removeMeshFromProject(self.sample_key)
        else:
            self.presenter.model.sample = self.old_sample


class InsertSampleFromFile(QtWidgets.QUndoCommand):
    def __init__(self, filename, presenter, combine):
        """ Command to insert sample model from a file to the sample list

        :param filename: path of file
        :type filename: str
        :param presenter: Mainwindow presenter instance
        :type presenter: sscanss.ui.windows.main.presenter.MainWindowPresenter
        :param combine: when True model is added to current otherwise replaces it
        :type combine: bool
        """
        super().__init__()

        self.filename = filename
        self.presenter = presenter
        self.combine = combine

        base_name = os.path.basename(filename)
        name, ext = os.path.splitext(base_name)
        ext = ext.replace('.', '').lower()
        self.sample_key = self.presenter.model.uniqueKey(name, ext)
        self.setText('Insert {}'.format(base_name))

    def redo(self):
        if not self.combine:
            self.old_sample = self.presenter.model.sample
        load_sample_args = [self.filename, self.combine]
        self.presenter.view.showProgressDialog('Loading 3D Model')
        self.worker = Worker(self.presenter.model.loadSample, load_sample_args)
        self.worker.job_succeeded.connect(self.onImportSuccess)
        self.worker.finished.connect(self.presenter.view.progress_dialog.close)
        self.worker.job_failed.connect(self.onImportFailed)
        self.worker.start()

    def undo(self):
        if self.combine:
            self.presenter.model.removeMeshFromProject(self.sample_key)
        else:
            self.presenter.model.sample = self.old_sample

    def onImportSuccess(self):
        if len(self.presenter.model.sample) > 1:
            self.presenter.view.docks.showSampleManager()

    def onImportFailed(self, exception):
        msg = 'An error occurred while loading the 3D model.\n\n' \
              'Please check that the file is valid.'

        logging.error(msg, exc_info=exception)
        self.presenter.view.showErrorMessage(msg)

        # Remove the failed command from the undo_stack
        self.setObsolete(True)
        self.presenter.view.undo_stack.undo()


class DeleteSample(QtWidgets.QUndoCommand):
    def __init__(self, sample_key, presenter):
        """ Command to delete sample model from sample list

        :param sample_key: key(s) of sample(s) to delete
        :type sample_key: List[str]
        :param presenter: Mainwindow presenter instance
        :type presenter: sscanss.ui.windows.main.presenter.MainWindowPresenter
        """
        super().__init__()

        self.keys = sample_key
        self.model = presenter.model
        self.old_keys = list(self.model.sample.keys())

        if len(sample_key) > 1:
            self.setText('Delete {} Samples'.format(len(sample_key)))
        else:
            self.setText('Delete {}'.format(sample_key[0]))

    def redo(self):
        self.deleted_mesh = {}
        for key in self.keys:
            self.deleted_mesh[key] = self.model.sample[key]

        self.model.removeMeshFromProject(self.keys)

    def undo(self):
        new_sample = {}
        for key in self.old_keys:
            if key in self.model.sample:
                new_sample[key] = self.model.sample[key]
            elif key in self.deleted_mesh:
                new_sample[key] = self.deleted_mesh[key]

        self.model.sample = OrderedDict(new_sample)


class MergeSample(QtWidgets.QUndoCommand):
    def __init__(self, sample_key, presenter):
        """ Command to merge sample models into a single one

        :param sample_key: key(s) of sample(s) to merge
        :type sample_key: List[str]
        :param presenter: Mainwindow presenter instance
        :type presenter: sscanss.ui.windows.main.presenter.MainWindowPresenter
        """
        super().__init__()

        self.keys = sample_key
        self.model = presenter.model
        self.new_name = self.model.uniqueKey('merged')
        self.old_keys = list(self.model.sample.keys())

        self.setText('Merge {} Samples'.format(len(sample_key)))

    def redo(self):
        self.merged_mesh = []
        samples = self.model.sample
        new_mesh = samples.pop(self.keys[0], None)
        self.merged_mesh.append((self.keys[0], 0))
        for i in range(1, len(self.keys)):
            old_mesh = samples.pop(self.keys[i], None)
            self.merged_mesh.append((self.keys[i], new_mesh.indices.size))
            new_mesh.append(old_mesh)

        self.model.addMeshToProject(self.new_name, new_mesh, combine=True)

    def undo(self):
        mesh = self.model.sample.pop(self.new_name, None)
        temp = {}
        for key, index in reversed(self.merged_mesh):
            temp[key] = mesh.splitAt(index) if index != 0 else mesh

        new_sample = {}
        for key in self.old_keys:
            if key in self.model.sample:
                new_sample[key] = self.model.sample[key]
            elif key in temp:
                new_sample[key] = temp[key]

        self.model.sample = OrderedDict(new_sample)


class ChangeMainSample(QtWidgets.QUndoCommand):
    def __init__(self, sample_key, presenter):
        """ Command to make a specified sample model the main one.

        :param sample_key: key of sample to make main
        :type sample_key: str
        :param presenter: Mainwindow presenter instance
        :type presenter: sscanss.ui.windows.main.presenter.MainWindowPresenter
        """
        super().__init__()

        self.key = sample_key
        self.model = presenter.model
        self.old_keys = list(self.model.sample.keys())
        self.new_keys = list(self.model.sample.keys())
        self.new_keys.insert(0, self.key)
        self.new_keys = list(dict.fromkeys(self.new_keys))

        self.setText('Set {} as Main Sample'.format(self.key))

    def redo(self):
        self.reorderSample(self.new_keys)

    def undo(self):
        self.reorderSample(self.old_keys)

    def mergeWith(self, command):
        """ Merges consecutive change main commands

        :param command: command to merge
        :type command: QUndoCommand
        :return: True if merge was successful
        :rtype: bool
        """
        self.new_keys = command.new_keys
        self.setText('Set {} as Main Sample'.format(self.key))

        return True

    def reorderSample(self, new_keys):
        new_sample = {}
        for key in new_keys:
            if key in self.model.sample:
                new_sample[key] = self.model.sample[key]

        self.model.sample = OrderedDict(new_sample)

    def id(self):
        """ Returns ID used when merging commands"""
        return 1000


class InsertFiducialsFromFile(QtWidgets.QUndoCommand):
    def __init__(self, filename, presenter):
        super().__init__()

        self.filename = filename
        self.presenter = presenter

        self.old_count = len(self.presenter.model.fiducials)

        self.setText('Import Fiducial Points')

    def redo(self):
        load_fiducials_args = [self.filename]
        self.presenter.view.showProgressDialog('Loading Fiducial Points')
        self.worker = Worker(self.presenter.model.loadFiducials, load_fiducials_args)
        self.worker.job_succeeded.connect(self.onImportSuccess)
        self.worker.finished.connect(self.presenter.view.progress_dialog.close)
        self.worker.job_failed.connect(self.onImportFailed)
        self.worker.start()

    def undo(self):
        current_count = len(self.presenter.model.fiducials)
        self.presenter.model.removePointsFromProject(slice(self.old_count, current_count, None))

    def onImportSuccess(self):
        self.presenter.view.docks.showPointManager()

    def onImportFailed(self, exception):
        msg = 'An error occurred while loading the fiducial points.\n\n' \
              'Please check that the file is valid.'

        logging.error(msg, exc_info=exception)
        self.presenter.view.showErrorMessage(msg)

        # Remove the failed command from the undo_stack
        self.setObsolete(True)
        self.presenter.view.undo_stack.undo()


class InsertFiducials(QtWidgets.QUndoCommand):
    def __init__(self, points, presenter):
        super().__init__()

        self.points = points
        self.presenter = presenter
        self.old_count = len(self.presenter.model.fiducials)

        self.setText('Add Fiducial Points')

    def redo(self):
        self.presenter.model.addPointsToProject(self.points)

    def undo(self):
        current_count = len(self.presenter.model.fiducials)
        self.presenter.model.removePointsFromProject(slice(self.old_count, current_count, None))


class DeleteFiducials(QtWidgets.QUndoCommand):
    def __init__(self, indices, presenter):
        super().__init__()

        self.indices = sorted(indices)
        self.model = presenter.model

        if len(self.indices) > 1:
            self.setText('Delete {} Fiducial Points'.format(len(self.indices)))
        else:
            self.setText('Delete Fiducial Point')

    def redo(self):
        self.old_values = self.model.fiducials[self.indices]
        self.model.removePointsFromProject(self.indices)

    def undo(self):
        fiducials = self.model.fiducials
        for index, value in enumerate(self.indices):
            if index < len(fiducials):
                fiducials = np.insert(fiducials, value, self.old_values[index], 0)
            else:
                temp = np.rec.array(self.old_values[index], dtype=self.model.point_dtype)
                fiducials = np.append(fiducials, temp)

        self.model.fiducials = fiducials.view(np.recarray)


class MoveFiducials(QtWidgets.QUndoCommand):
    def __init__(self, move_from, move_to, presenter):
        super().__init__()

        self.move_from = move_from
        self.move_to = move_to
        self.model = presenter.model
        self.old_order = list(range(0, len(self.model.fiducials)))
        self.new_order = list(range(0, len(self.model.fiducials)))
        self.new_order[move_from], self.new_order[move_to] = self.new_order[move_to], self.new_order[move_from]

        self.setText('Change Fiducial Point Index')

    def redo(self):
        fiducial = self.model.fiducials
        fiducial[self.old_order] = fiducial[self.new_order]
        self.model.fiducials = fiducial  # emits fiducial_changed signal

    def undo(self):
        fiducial = self.model.fiducials
        fiducial[self.new_order] = fiducial[self.old_order]
        self.model.fiducials = fiducial  # emits fiducial_changed signal

    def mergeWith(self, command):
        move_to = command.move_to
        move_from = command.move_from
        self.new_order[move_from], self.new_order[move_to] = self.new_order[move_to], self.new_order[move_from]

        return True

    def id(self):
        """ Returns ID used when merging commands"""
        return 1001


class EditFiducials(QtWidgets.QUndoCommand):
    def __init__(self, row, value, presenter):
        super().__init__()

        self.model = presenter.model

        temp = (np.copy(self.model.fiducials.points[row]), self.model.fiducials.enabled[row])
        self.old_values = {row: temp}
        self.new_values = {row: value}

        self.setText('Change Fiducial Point Index')

    def redo(self):
        fiducial = self.model.fiducials
        for key, value in self.new_values.items():
            fiducial[key] = value

        self.model.fiducials = fiducial  # emits fiducial_changed signal

    def undo(self):
        fiducial = self.model.fiducials
        for key, value in self.old_values.items():
            fiducial[key] = value

        self.model.fiducials = fiducial  # emits fiducial_changed signal

    def mergeWith(self, command):
        self.new_values.update(command.new_values)
        command.old_values.update(self.old_values)
        self.old_values = command.old_values

        return True

    def id(self):
        """ Returns ID used when merging commands"""
        return 1002


