# SSE: Modified to encompass the outside-vendor-provided
# tk-maya-playblast app functionailty, which we had also customized to fit
# our requirements.
# linter: flake8
# docstring style: Google
# (DW 2020-08-05)

import sgtk
from sgtk.platform.qt import QtCore
from sgtk.platform.qt import QtGui

import os

HookBaseClass = sgtk.get_hook_baseclass()

INITIAL_PB_STATUS = 'arev'
TIME_STR_FMT = '%Y-%m-%d (%A) %H.%M %p'


class SubmitterSGTK(HookBaseClass):
    """
    This hook allows submitting a Version to Shotgun using Shotgun Toolkit.
    """
    def __init__(self, *args, **kwargs):
        super(SubmitterSGTK, self).__init__(*args, **kwargs)

        self.__app = self.parent

        self._upload_to_shotgun = self.__app.get_setting('upload_to_shotgun')
        self._store_on_disk = self.__app.get_setting('store_on_disk')

    def can_submit(self):
        """Check if it's possible to submit versions given the current
        context/environment.

        Returns:
            bool: Flag telling if the hook can submit a version.
        """
        msg = 'Application is not configured to store images on disk or '
        msg += 'upload to shotgun!'
        if not self._upload_to_shotgun and not self._store_on_disk:
            QtGui.QMessageBox(
                QtGui.QMessageBox.Warning,
                'Cannot submit to Shotgun',
                msg,
                flags=QtCore.Qt.Dialog
                | QtCore.Qt.MSWindowsFixedSizeDialogHint
                | QtCore.Qt.WindowStaysOnTopHint
                | QtCore.Qt.X11BypassWindowManagerHint,
            ).exec_()

            return False

        return True

    def submit_version(
        self,
        path_to_frames,
        path_to_movie,
        thumbnail_path,
        sg_publishes,
        sg_task,
        description,
        first_frame,
        last_frame,
    ):
        """Create a version in Shotgun for a given path and linked to the
        specified publishes.

        Args:
            path_to_frames (str): Path to the frames.
            path_to_movie (str): Path to the movie.
            thumbnail_path (str): Path to the thumbnail representing the
                version.
            sg_publishes (list): Published files to be linked to the version.
            sg_task (dict): Task to be linked to the version.
            description (str): Description of the version.
            first_frame (int): Version first frame.
            last_frame (int): Version last frame.

        Returns:
            dict: The Version Shotgun entity dictionary that was created.
        """
        self.sg_version = None
        self.thumbnail_path = thumbnail_path

        # get current shotgun user
        current_user = sgtk.util.get_current_user(self.__app.sgtk)

        # create a name for the version based on the file name
        # grab the file name, strip off extension, do some replacements,
        # and capitalize
        name = os.path.splitext(os.path.basename(path_to_movie))[0]
        name = name.replace('_', ' ')
        name = name.capitalize()

        # create the version in Shotgun
        ctx = self.__app.context

        # data defaults
        self.data = {}
        self.data['code'] = name

        self.data['sg_status_list'] = self.__app.get_setting(
            'new_version_status'
        )

        self.data['entity'] = ctx.entity
        self.data['sg_task'] = sg_task
        self.data['sg_first_frame'] = first_frame
        self.data['sg_last_frame'] = last_frame
        self.data['sg_frames_have_slate'] = False
        self.data['created_by'] = current_user
        self.data['user'] = current_user
        self.data['sg_path_to_frames'] = path_to_frames
        self.data['sg_movie_has_slate'] = True
        self.data['project'] = ctx.project

        if not description:
            description = ''
        self.data['description'] = description

        if first_frame and last_frame:
            self.data['frame_count'] = last_frame - first_frame + 1
            self.data['frame_range'] = '{0}-{1}'.format(
                first_frame,
                last_frame
            )

        _ft = 'PublishedFile'
        if sgtk.util.get_published_file_entity_type(self.__app.sgtk) == _ft:
            self.data['published_files'] = sg_publishes
        else:
            # for type 'TankPublishedFile'
            len_pub = len(sg_publishes)
            if len_pub > 0:
                if len_pub > 1:
                    msg = '>> Only the first publish of {} '.format(len_pub)
                    msg += 'can be registered for the new version!'
                    self.__app.log_warning(msg)
                self.data['tank_published_file'] = sg_publishes[0]

        if self._store_on_disk:
            self.local_path_to_movie = path_to_movie
            self.data['sg_path_to_movie'] = path_to_movie

        # check if we're in a tk-maya engine, act accordingly
        current_engine = sgtk.platform.current_engine()
        if current_engine.name == 'tk-maya':
            # playblast submit dialog in maya
            try:
                self.playblast_submit_dialog()
                m = '>> playblast_submit_dialog > {}'.format(self.dialog)
                self.logger.info(m)
            except Exception as e:
                m = '>> playblast_submit_dialog failed > {}'.format(str(e))
                self.logger.info(m)
        else:
            # 'orignal hook style' submit
            self.create_sg_version()

        return self.sg_version

    def create_sg_version(self):
        """Create a Version in Shotgun for a given path, and upload the
        specified movie + thumbnail.
        """
        # check if a version entity with same code already exists in Shotgun,
        # if not, create a new version
        sg_filters = [
            ['code', 'is', self.data['code']]
        ]

        found_vers = self.__app.sgtk.shotgun.find_one('Version', sg_filters)
        if found_vers:
            # updating, remove keys that can't be updated
            pop_keys = [
                'created_by'
            ]
            for pop_key in pop_keys:
                self.data.pop(pop_key, None)

            # update
            self.sg_version = self.__app.sgtk.shotgun.update(
                'Version',
                found_vers['id'],
                self.data
            )

            msg = '>> Found & updated existing version > {}'.format(found_vers)
            self.logger.info(msg)
        else:
            # create
            self.sg_version = self.__app.sgtk.shotgun.create(
                'Version',
                self.data
            )

            msg = '>> Created version in shotgun > {}'.format(str(self.data))
            msg += '\n>> sg_version > {}'.format(self.sg_version)
            self.logger.info(msg)

        # upload files:
        self._upload_files()

        # remove from filesystem if required
        if not self._store_on_disk and os.path.exists(
            self.local_path_to_movie
        ):
            os.unlink(self.local_path_to_movie)

        return self.sg_version

    def _upload_files(self):
        """Upload the required files to Shotgun.
        """
        # upload in a new thread and make our own event loop to wait for the
        # thread to finish.
        event_loop = QtCore.QEventLoop()
        thread = UploaderThread(
            self.__app,
            self.sg_version,
            self.local_path_to_movie,
            self.thumbnail_path,
            self._upload_to_shotgun
        )
        thread.finished.connect(event_loop.quit)
        thread.start()
        event_loop.exec_()

        # log any errors generated in the thread
        for e in thread.get_errors():
            self.__app.log_error(e)

    def maya_shot_playblast_version(self):
        """Wrapper for playblast to Shotgun Version methods (customize the
        Version publish data, create a Version in Shotgun, close the 'Playblast
        to Shotgun' dialog).
        """
        self.maya_shot_playblast_publish_data()
        self.create_sg_version()
        self.copy_local_files_to_server()
        self.dialog.done(0)

    def maya_shot_playblast_publish_data(self):
        """Modify some of the playblast media publish values prior to publish
        for SSE requirements, for the following keys:
        - sg_movie_has_slate
        - sg_status_list
        - code
        - description
        - sg_path_to_movie
        """
        import maya.cmds as cmds
        from datetime import datetime

        # simple key values
        self.data['sg_movie_has_slate'] = False
        self.data['sg_status_list'] = INITIAL_PB_STATUS

        # 'code' modification for version addition
        new_code = os.path.basename(self.data['sg_path_to_movie'])
        self.data['code'] = new_code

        # 'description' modification for comments, user, host, and
        # datetime additions
        artist_comments = self.dialog.textEdit_comments.toPlainText()
        o_desc = artist_comments.strip()

        current_time = datetime.now().strftime(TIME_STR_FMT)
        user_name = os.environ.get('USERNAME', 'unknown')
        host_name = os.environ.get('COMPUTERNAME', 'unknown')

        desc_mod = 'Publish by {0} at {1} on {2}'.format(
            user_name,
            host_name,
            current_time
        )

        new_desc = '{0}\n\n{1}'.format(o_desc, desc_mod)
        self.data['description'] = new_desc

        # 'path' modification for template output fields addition
        # TODO: make all the template query stuff its own method, probably
        scene_name = cmds.file(q=True, sn=True)
        wk_template = self.__app.sgtk.templates.get('maya_shot_work')
        pb_template = self.__app.sgtk.templates.get('maya_shot_playblast')
        wk_fields = wk_template.get_fields(scene_name)
        self.data['sg_path_to_movie'] = pb_template.apply_fields(wk_fields)

        # add an attribute for use with later copying of local file to
        # versionless editorial destination
        sq_template = self.__app.sgtk.templates.get('maya_sequence_playblast')
        self.editorial_path_to_movie = sq_template.apply_fields(wk_fields)

    def copy_local_files_to_server(self):
        """Copy the local playblast file to targets defined by templates.yml,
        stored previously as attributes.
        """
        import shutil

        lcl = self.local_path_to_movie
        dsts = [
            self.data['sg_path_to_movie'],
            self.editorial_path_to_movie
        ]

        for dst in dsts:
            try:
                # make sure that destination folders exist
                dst_dirname = os.path.dirname(dst)
                if not os.path.exists(dst_dirname):
                    os.makedirs(dst_dirname)

                shutil.copy(lcl, dst)
                m = '>> Copied {0} > {1}'.format(lcl, dst)
                self.logger.info(m)
            except Exception as e:
                m = '>> Copy failed {0} > {1} > {2}'.format(
                    lcl,
                    dst,
                    str(e)
                )
                self.logger.info(m)

    def playblast_submit_dialog(self):
        """A dialog UI widget that allows the user to enter comments and then
        initiate the upload to Shotgun as a Version if they choose, by entering
        text + clicking the button. Intercepts before the standard upload.
        NOTE: sgtk's implementation of Qt doesn't have libraries available for
        using .ui files directly, so we have to program it explicitly.
        """
        # main dialog
        self.dialog = QtGui.QDialog(
            None,
            QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint
        )

        self.dialog.setObjectName('PlayblastDialog')
        self.dialog.resize(440, 240)
        self.dialog.setMinimumSize(QtCore.QSize(440, 240))
        self.dialog.setMaximumSize(QtCore.QSize(440, 240))

        self.dialog.setWindowFlags(
            self.dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint
        )

        self.dialog.setWindowTitle(
            QtGui.QApplication.translate(
                'PlayblastDialog',
                'Playblast to Shotgun - Sinking Ship',
                None,
                QtGui.QApplication.UnicodeUTF8
            )
        )

        # main layout & grid
        self.dialog.gridLayoutWidget = QtGui.QWidget(self.dialog)
        self.dialog.gridLayoutWidget.setGeometry(QtCore.QRect(9, 9, 421, 221))
        self.dialog.gridLayoutWidget.setObjectName('gridLayoutWidget')

        self.dialog.gridLayout_main = QtGui.QGridLayout(
            self.dialog.gridLayoutWidget
        )

        self.dialog.gridLayout_main.setContentsMargins(0, 0, 0, 0)
        self.dialog.gridLayout_main.setObjectName('gridLayout_main')

        # upload button
        self.dialog.pushButton_upload = QtGui.QPushButton(
            self.dialog.gridLayoutWidget
        )
        self.dialog.pushButton_upload.setObjectName('pushButton_upload')

        self.dialog.pushButton_upload.setText(
            QtGui.QApplication.translate(
                'PlayblastDialog',
                'Upload as Version to Shotgun',
                None,
                QtGui.QApplication.UnicodeUTF8
            )
        )

        self.dialog.gridLayout_main.addWidget(
            self.dialog.pushButton_upload,
            2,
            0,
            1,
            1
        )

        # comments groupbox
        self.dialog.groupBox_comments = QtGui.QGroupBox(
            self.dialog.gridLayoutWidget
        )

        self.dialog.groupBox_comments.setAlignment(QtCore.Qt.AlignCenter)
        self.dialog.groupBox_comments.setFlat(False)
        self.dialog.groupBox_comments.setObjectName('groupBox_comments')

        self.dialog.groupBox_comments.setTitle(
            QtGui.QApplication.translate(
                'PlayblastDialog',
                'Artist Comments',
                None,
                QtGui.QApplication.UnicodeUTF8
            )
        )

        # comments textedit
        self.dialog.textEdit_comments = QtGui.QTextEdit(
            self.dialog.groupBox_comments
        )

        self.dialog.textEdit_comments.setGeometry(
            QtCore.QRect(12, 20, 395, 131)
        )

        self.dialog.textEdit_comments.setMinimumSize(QtCore.QSize(395, 131))
        self.dialog.textEdit_comments.setMaximumSize(QtCore.QSize(395, 131))
        self.dialog.textEdit_comments.setObjectName('textEdit_comments')

        self.dialog.gridLayout_main.addWidget(
            self.dialog.groupBox_comments,
            1,
            0,
            1,
            1
        )

        # signals and slots
        self.dialog.pushButton_upload.clicked.connect(
            self.maya_shot_playblast_version
        )

        # launch dialog
        self.dialog.exec_()


class UploaderThread(QtCore.QThread):
    """
    Simple worker thread that encapsulates uploading to shotgun.
    Broken out of the main loop so that the UI can remain responsive
    even though an upload is happening.
    """
    def __init__(
        self,
        app,
        version,
        path_to_movie,
        thumbnail_path,
        upload_to_shotgun
    ):
        QtCore.QThread.__init__(self)
        self._app = app
        self._version = version
        self._path_to_movie = path_to_movie
        self._thumbnail_path = thumbnail_path
        self._upload_to_shotgun = upload_to_shotgun
        self._errors = []

    def get_errors(self):
        """Returns the errors collected while uploading files to Shotgun.

        Returns:
            list: List of errors.
        """
        return self._errors

    def run(self):
        """This function implements what get executed in the UploaderThread.
        """
        upload_error = False

        if self._upload_to_shotgun:
            try:
                self._app.sgtk.shotgun.upload(
                    'Version',
                    self._version['id'],
                    self._path_to_movie,
                    'sg_uploaded_movie',
                )
            except Exception as e:
                m = '>> Movie upload to Shotgun failed > {}'.format(str(e))
                self._errors.append(m)
                upload_error = True

        if not self._upload_to_shotgun or upload_error:
            try:
                self._app.sgtk.shotgun.upload_thumbnail(
                    'Version', self._version['id'], self._thumbnail_path
                )
            except Exception as e:
                m = ">> Thumbnail upload to Shotgun failed > {}".format(str(e))
                self._errors.append(m)
