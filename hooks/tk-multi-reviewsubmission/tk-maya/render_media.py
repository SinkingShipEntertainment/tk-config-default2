# SSE: Modified to encompass the outside-vendor-provided
# tk-maya-playblast app functionailty, which we had also customized to fit
# our requirements.
# linter: flake8
# docstring style: Google
# (DW 2020-07-30)

import sgtk
import os
import re
import heapq
import tempfile

import maya.cmds as cmds
import pymel.core as pm

from datetime import datetime
from sgtk.platform.qt import QtCore
from sgtk.platform.qt import QtGui

HookBaseClass = sgtk.get_hook_baseclass()

# global variables
CAMERA_NAME_PATTERN = r'\w+:TRACKCAMShape'
CURR_PROJECT = os.environ['CURR_PROJECT']
DEFAULT_HEIGHT = 720
DEFAULT_WIDTH = 1280
PLAYBLAST_WINDOW = 'Playblast_Window'
TIME_STR_FMT = '%Y-%m-%d (%A) %H.%M %p'


MODEL_EDITOR_PARAMS = {
    'activeView': True,
    'backfaceCulling': False,
    'cameras': False,
    'controlVertices': False,
    'deformers': False,
    'dimensions': False,
    'displayAppearance': 'smoothShaded',
    'displayLights': 'default',
    'displayTextures': True,
    'dynamicConstraints': False,
    'fogging': False,
    'follicles': False,
    'grid': False,
    'handles': False,
    'headsUpDisplay': True,
    'hulls': False,
    'ignorePanZoom': False,
    'ikHandles': False,
    'imagePlane': True,
    'joints': False,
    'lights': False,
    'locators': False,
    'manipulators': False,
    'nParticles': False,
    'nurbsCurves': True,
    'nurbsSurfaces': False,
    'pivots': False,
    'planes': False,
    'rendererName': 'vp2Renderer',
    'selectionHiliteDisplay': False,
    'shadows': False,
    'sortTransparent': True,
    'strokes': True,
    'textures': True,
    'twoSidedLighting': False,
    'useDefaultMaterial': False,
    'wireframeOnShaded': False,
}

PLAYBLAST_PARAMS = {
    'forceOverwrite': True,
    'format': 'qt',
    'framePadding': 4,
    'compression': 'H.264',
    'offScreen': True,
    'percent': 100,
    'showOrnaments': True,
    'viewer': True,
    'sequenceTime': 0,
    'clearCache': True,
    'quality': 70,
}


class RenderMedia(HookBaseClass):
    """
    RenderMedia hook implementation for the tk-maya engine.
    """
    def __init__(self, *args, **kwargs):
        super(RenderMedia, self).__init__(*args, **kwargs)

        self.__app = self.parent

    def render(
        self,
        input_path,
        output_path,
        width,
        height,
        first_frame,
        last_frame,
        version,
        name,
        color_space,
    ):
        """Render the media using the Maya Playblast API.

        Args:
            input_path (str): Path to the input frames for the movie. (Unused)
            output_path (str): Path to the output movie that will be rendered.
            width (int): Width of the output movie. (Unused)
            height (int): Height of the output movie. (Unused)
            first_frame (int): The first frame of the sequence of frames.
                (Unused)
            last_frame (int): The last frame of the sequence of frames.
                (Unused)
            version (int): Version number to use for the output movie slate and
                burn-in.
            name (str): Name to use in the slate for the output movie.
            color_space (str): Colorspace of the input frames. (Unused)

        Raises:
            RuntimeError: Unable to find playblast file on disk.
            RuntimeError: Custom playblast window creation failed.
            RuntimeError: Not a valid Shotgun Shot in current Project.

        Returns:
            str: Location of the rendered media.
        """
        fail_head = '>> Failed to create a playblast'

        if self.is_valid_shot():
            # name of the playblast file
            if name == 'Unnamed':
                current_file_path = cmds.file(query=True, sn=True)

                if current_file_path:
                    # just the file without the maya extension
                    name = os.path.basename(current_file_path)
                    name = os.path.splitext(name)[0]
                    name = '{}.mov'.format(name)

            if not output_path:
                output_path = self._get_temp_media_path(name, version, '')

            playblast_args = self.get_default_playblast_args(output_path)

            m = '>> Playblast arguments > {0} using ({1})'.format(
                output_path,
                playblast_args
            )
            self.logger.info(m)

            # custom playblast window
            create_window = self.create_window()
            if create_window:
                pb_success = False

                # set required visible HUDs
                v_huds = self.set_huds(action='set')

                # hide all controls groups
                self.set_ctrls_visibility(switch_val=0)

                # playblast
                output_path = ''
                try:
                    output_path = pm.playblast(**playblast_args)
                    m = '>> Playblast succeeded > {}'.format(output_path)
                    self.logger.info(m)
                    pb_success = True
                except Exception as e:
                    m = '>> Playblast failed > {}'.format(str(e))
                    self.logger.info(m)
                finally:
                    # clean up
                    self.set_ctrls_visibility(switch_val=1)
                    self.set_huds(action='unset', v_huds=v_huds)
                    self.restore_overscan()
                    self.destroy_window()
                    m = '>> Post-playblast-attempt cleanup finished'
                    self.logger.info(m)

                if pb_success:
                    # find the file on disk, return output_path
                    # TODO: make this its own method, probably
                    o_split = os.path.split(playblast_args['filename'])
                    o_folder = o_split[0]
                    o_file = o_split[1]

                    files = []
                    for f in os.listdir(o_folder):
                        f_path = os.path.join(o_folder, f)

                        if not f.startswith(o_file) or \
                                not os.path.isfile(f_path):
                            continue

                        try:
                            # the following call raises an OSError if the file
                            # does not exist or is somehow inaccessible
                            m_time = os.path.getmtime(f_path)
                        except OSError:
                            continue
                        else:
                            # insert with a negative access time so the first
                            # element in the list is the most recent file
                            heapq.heappush(
                                files,
                                (-m_time, f)
                            )

                    if files:
                        f = heapq.heappop(files)[1]
                        output_path = os.path.join(o_folder, f)

                        m = '>> Playblast written to > {}'.format(output_path)
                        self.logger.info(m)

                        return output_path

                    # not found
                    m = '{}. Unable to find it on disk.'.format(fail_head)
                    raise RuntimeError(m)
            else:
                m = '{}. Custom window creation failed.'.format(fail_head)
                raise RuntimeError(m)
        else:
            m = '{}. Not a valid Shot in Project {}.'.format(
                fail_head,
                CURR_PROJECT
            )
            raise RuntimeError(m)

    def _get_temp_media_path(self, name, version, extension):
        """Build a temporary path to put the rendered media.

        Args:
            name (str): Name of the media being rendered.
            version (str): Version number of the media being rendered.
            extension (str): Extension of the media being rendered.

        Returns:
            str: Temporary path to output the rendered version.
        """
        temp_dir = tempfile.gettempdir()
        temp_media_path = '{0}\\{1}'.format(temp_dir, name)

        return temp_media_path

    def is_valid_shot(self):
        """Check to see if the open Maya file is from a valid Shot file.

        Returns:
            bool: True if the open Maya file is from a Shotgun Toolkit Primary
                storage location, otherwise False.
        """
        valid_shot = False
        primary_dir = 'N:/projects/{}/sequences'.format(CURR_PROJECT)

        maya_file = cmds.file(q=True, sn=True)
        file_parts = maya_file.split('/')
        if os.path.exists(maya_file) and len(file_parts) == 11:
            sub_dirs = '/'.join(file_parts[4:9])
            chk_dir = '{0}/{1}'.format(primary_dir, sub_dirs)

            if maya_file.startswith(chk_dir):
                valid_shot = True

        return valid_shot

    def get_default_playblast_args(self, output_path):
        """Returns a dictionary of playblast arguments key/value pairs, using
        values that are specific to SSE's requirements, e.g. H.264, never use
        '.iff' sequences, etcetera.

        For more information about the playblast API:
        https://help.autodesk.com/view/MAYAUL/2020/ENU/...
                                       ...?guid=__CommandsPython_playblast_html

        For more information: about the doPlayblastArgList mel function, look
        at the doPlayblastArgList.mel in the Autodesk Maya app bundle.

        Args:
            output_path (str): Path to the output movie that will be
            rendered.

        Returns:
            dict: Playblast arguments.
        """
        playblast_args = PLAYBLAST_PARAMS
        playblast_args['filename'] = output_path
        playblast_args['width'] = DEFAULT_WIDTH
        playblast_args['height'] = DEFAULT_HEIGHT

        # frame range
        playblast_args['startTime'] = float(1)

        end_frame = self.get_shot_endframe()
        playblast_args['endTime'] = float(end_frame)

        # include audio if available
        audio_list = pm.ls(type='audio')
        if audio_list:
            playblast_args['sound'] = audio_list[0]

        return playblast_args

    def get_shot_endframe(self):
        """Queries Shotgun for the end frame value of the Shot, if you're in a
        Shot context in Maya, and if there's a value to be had. Otherwise,
        returns an int value of 1.

        Returns:
            int: End frame in Shotgun.
        """
        end_frame = 1

        if self.is_valid_shot():
            ctx = self.__app.context

            shot_ent = ctx.entity
            shot_name = shot_ent['name']

            sg_filters = [['id', 'is', shot_ent['id']]]
            sg_fields = ['sg_cut_out']

            sg_shot = self.__app.shotgun.find_one(
                'Shot',
                sg_filters,
                sg_fields
            )
            if sg_shot:
                end_frame_chk = sg_shot['sg_cut_out']
                if isinstance(end_frame_chk, int):
                    end_frame = end_frame_chk

                    m = '>> Shotgun end frame for {0} > {1}'.format(
                        shot_name,
                        end_frame
                    )
                    self.logger.info(m)

        return end_frame

    def destroy_window(self):
        """If the PLAYBLAST_WINDOW exists, destroy it (window and its prefs).
        """
        try:
            pm.deleteUI(PLAYBLAST_WINDOW)
            m = '>> Found and deleted existing window > {}'.format()
            self.logger.info(m)
        except Exception:
            pass

        if pm.windowPref(PLAYBLAST_WINDOW, exists=True):
            pm.windowPref(PLAYBLAST_WINDOW, remove=True)

    def create_window(self):
        """Create a custom window with related modelEditor, as well as running
        the pre- and post-window methods.

        Returns:
            bool: Success of the window, modelEditor, and pre- and post-
                window methods.
        """
        w_success = False

        # call various pre-window methods
        cam_check = self.set_camera()
        if cam_check:
            self.set_imageplanes_colorspace()
            self.set_vp2_globals()

            try:
                # create window (clean up first)
                self.destroy_window()

                window = pm.window(
                    PLAYBLAST_WINDOW,
                    titleBar=True,
                    iconify=True,
                    leftEdge=100,
                    topEdge=100,
                    width=DEFAULT_WIDTH,
                    height=DEFAULT_HEIGHT,
                    sizeable=False
                )

                # create window model editor
                layout = pm.formLayout()
                editor = pm.modelEditor(**MODEL_EDITOR_PARAMS)
                pm.setFocus(editor)

                pm.formLayout(
                    layout,
                    edit=True,
                    attachForm=(
                        (editor, "left", 0),
                        (editor, "top", 0),
                        (editor, "right", 0),
                        (editor, "bottom", 0)
                    )
                )

                # show window
                pm.setFocus(editor)
                pm.showWindow(window)
                pm.refresh()

                # call various post-window methods
                self.generate_all_uv_tile_previews()

                # success!
                w_success = True
            except Exception as e:
                m = '>> Failed to create playblast window > {}'.format(str(e))
                self.logger.info(m)

        return w_success

    def set_huds(self, action='set', v_huds=[]):
        """Depending on the requested action, either creates and sets new HUDs
        for playblast display, or returns all HUDs to their orignal settings
        pre-playblast.

        Args:
            action (str, optional): Set or unset the HUDs. Defaults to 'set'.
            v_huds (list, optional): Empty if action is 'set'; a list of
            originally-visible HUDs if action is 'unset'. Defaults to [].

        Returns:
            list: If action is 'set', returns a list of the originally-visible
                HUDs.
        """
        huds = pm.headsUpDisplay(listHeadsUpDisplays=True)

        if action == 'set':
            v_huds = [
                f for f in huds
                if pm.headsUpDisplay(f, query=True, vis=True)
            ]

            # hide all visible HUDs
            map(lambda f: pm.headsUpDisplay(f, edit=True, vis=False), v_huds)

            # add required HUD
            # user name
            edit_existing_hud = 'HUDUserName' in huds

            user_data = sgtk.util.get_current_user(self.__app.sgtk)
            user_name = user_data['login']
            self.logger.info('>> user_name > {}'.format(user_name))

            pm.headsUpDisplay(
                'HUDUserName',
                edit=edit_existing_hud,
                visible=True,
                label='User: {}'.format(user_name),
                section=8,
                block=1,
                blockSize='small',
                padding=0
            )

            # scene name
            edit_existing_hud = 'HUDSceneName' in huds
            sh_name = cmds.file(q=True, loc=True, shn=True).rsplit('.', 1)[0]

            pm.headsUpDisplay(
                'HUDSceneName',
                edit=edit_existing_hud,
                visible=True,
                label='Shot: {}'.format(sh_name),
                section=6,
                block=1,
                blockSize='small',
                padding=0
            )

            # focal length
            pm.headsUpDisplay(
                'HUDFocalLength',
                edit=True,
                visible=True,
                section=3,
                block=1,
                blockSize='small',
                padding=0
            )

            # current frame
            pm.headsUpDisplay(
                'HUDCurrentFrame',
                edit=True,
                visible=True,
                dataFontSize='large',
                section=8,
                block=0,
                blockSize='small',
                padding=0
            )

            # date & time
            # get the time at the point of playblast
            edit_existing_hud = 'HUDTime' in huds

            current_time = datetime.now().strftime(TIME_STR_FMT)
            pm.headsUpDisplay(
                'HUDTime',
                edit=edit_existing_hud,
                visible=True,
                label=current_time,
                section=6,
                block=0,
                blockSize='small',
                padding=0
            )

            return v_huds

        if action == 'unset':
            # hide the playblast-specific HUDs
            map(
                lambda f:
                    pm.headsUpDisplay(f, edit=True, visible=False),
                    huds
            )

            # show the originally visible HUDs again
            map(
                lambda f:
                    pm.headsUpDisplay(f, edit=True, visible=True),
                    v_huds
            )

    def restore_overscan(self):
        """Restore the original overscan value for the TRACKCAM camera (both
        the camera and its original overscan value have been stored).
        """
        try:
            cmds.camera(
                self.orig_cam,
                e=True,
                overscan=self.orig_cam_overscan
            )
            m = '>> Restored {0} overscan > {1}'.format(
                self.orig_cam,
                self.orig_cam_overscan
            )
            self.logger.info(m)
        except Exception as e:
            m = '>> Failed to restore {0} overscan > {1}'.format(
                self.orig_cam,
                str(e)
            )
            self.logger.info(m)

    def set_camera(self):
        """Find first camera matching pattern and set as active camera, also
        record the original overscan then set the required overscan.

        Returns:
            bool: Success at finding the TRACKCAM and recording its original
                overscan value.
        """
        success = False

        valid_cam_list = [
            c.name() for c in pm.ls(type='camera', r=True)
            if re.match(CAMERA_NAME_PATTERN, c.name())
        ]
        self.logger.info('>> camera_list > {}'.format(valid_cam_list))

        if valid_cam_list:
            w_cam = valid_cam_list[0]

            self.orig_cam = w_cam
            self.orig_cam_overscan = cmds.camera(
                w_cam,
                q=True,
                overscan=True
            )

            # camera overscan, etcetera settings required for playblast
            cmds.camera(
                w_cam,
                e=True,
                overscan=1.0,
                displayFieldChart=False,
                displaySafeAction=False,
                displaySafeTitle=False
            )

            # playblast params
            if 'cam' not in MODEL_EDITOR_PARAMS.keys():
                MODEL_EDITOR_PARAMS['cam'] = w_cam

            # success!
            success = True
        else:
            mb_title = 'Cannot Playblast to Shotgun'
            m = 'A referenced TRACKCAM is required for Shotgun playblasts.'
            self.messagebox_alert(mb_title, m)

            success = False

        return success

    def messagebox_alert(self, mb_title, mb_message):
        """Pop up a message box alert when needed.

        Args:
            mb_title (str): A title for the message box.
            mb_message (str): The message for the message box.
        """
        QtGui.QMessageBox(
            QtGui.QMessageBox.Warning,
            mb_title,
            mb_message,
            flags=QtCore.Qt.Dialog
            | QtCore.Qt.MSWindowsFixedSizeDialogHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.X11BypassWindowManagerHint,
        ).exec_()

    def set_vp2_globals(self):
        """Sets various Viewport2.0 attribute values, e.g. if a Maya
        useBackground shader is in the Maya file, turn off SSAO.
        """
        use_bg_exists = pm.ls(type='useBackground')
        hrg = pm.general.PyNode('hardwareRenderingGlobals')
        if use_bg_exists:
            hrg.ssaoEnable.set(0)
        else:
            hrg.ssaoEnable.set(1)
            hrg.ssaoRadius.set(32)
            hrg.ssaoFilterRadius.set(16)
            hrg.ssaoSamples.set(32)
        hrg.multiSampleEnable.set(1)

    def set_imageplanes_colorspace(self, c_type='sRGB'):
        """Method to set all imagePlanes colorspace, default is 'sRGB'.

        Args:
            c_type (str, optional): The colorspace type. Defaults to 'sRGB'.
        """
        im_planes = cmds.ls(type='imagePlane')
        for im_plane in im_planes:
            im_attr = '{}.colorSpace'.format(im_plane)
            try:
                cmds.setAttr(im_attr, c_type, type='string')
                self.logger.info('>> Set {0} > {1}'.format(im_attr, c_type))
            except Exception as e:
                m = '>> Could not set {0} > {1}'.format(im_attr, str(e))
                self.logger.info(m)

    def generate_all_uv_tile_previews(self, res_max=1024):
        """Regenerate all UV-tile preview textures.

        Args:
            res_max (int, optional): Maximum resolution. Defaults to 1024.
        """
        # set the resolution...
        try:
            hrg_texmax_attr = 'hardwareRenderingGlobals.textureMaxResolution'
            cmds.setAttr(hrg_texmax_attr, res_max)
            m = '>> Set {0} > {1}'.format(hrg_texmax_attr, res_max)
            self.logger.info(m)
        except Exception as e:
            m = '>> Failed to set {0} > {1}'.format(hrg_texmax_attr, str(e))
            self.logger.info(m)

        # generate for all file nodes in *RIG shaders...
        f_nodes = cmds.ls(typ='file')
        if f_nodes:
            for f_node in f_nodes:
                uvtm_attr = '{}.uvTilingMode'.format(f_node)
                uvtq_attr = '{}.uvTileProxyQuality'.format(f_node)

                uvtm_val = cmds.getAttr(uvtm_attr)
                uvtq_val = cmds.getAttr(uvtq_attr)
                if uvtm_val != 0 and uvtq_val != 0:
                    try:
                        cmds.ogs(rup=f_node)
                        m = '>> UV Tile Preview > {}'.format(f_node)
                        self.logger.info(m)
                    except Exception as e:
                        m = '>> Failed UV Tile Preview {0} > {1}'.format(
                            f_node,
                            str(e)
                        )
                        self.logger.info(m)

    def set_ctrls_visibility(self, switch_val=1):
        """Need to see NURBS curves in playblast for END2 character 'sparky',
        so leave them on in the viewport & hide/show any controls group in
        the active Maya scene file as a workaround.
        """
        # inconsitent naming in RIG controls group root nodes,
        # unfortunately (get Assets dept. to standardize in
        # future)...
        grp_root_nodes = [
            '*:controls',           # --- is this what should be standard?
            '*:controls_gr',        # --- ...or is this correct?
            '*:control_gr',         # --- sometimes e.g. DroneRobot_RIG v005
            '*:model_controls_gr',  # --- sometimes e.g. Ling_RIG v048
            '*:model_rig_gr',       # --- no idea e.g. Ling_RIG v050
            '*:Controls',           # --- legacy rigs e.g. Dragon_RIG v036
            '*:rig'                 # --- guidelines e.g. PolarBear_RIG v050
        ]

        all_ctrl_grps = cmds.ls(grp_root_nodes)
        for a_ctrl_grp in all_ctrl_grps:
            grp_attr = '{}.visibility'.format(a_ctrl_grp)
            try:
                cmds.setAttr(grp_attr, switch_val)
            except Exception as e:
                self.logger.info(str(e))

        # compensating for nurbsCurves that fall outside of references
        # (e.g. in-scene duplicates of RIG control curves, animator
        # created curves, etc.)...
        all_ncurves = cmds.ls(type='nurbsCurve')
        nr_ncurves = [
            _n for _n in all_ncurves if not cmds.referenceQuery(_n, inr=True)
        ]
        if nr_ncurves:
            for _nr in nr_ncurves:
                _nr_attr = '{}.visibility'.format(_nr)
                cmds.setAttr(_nr_attr, switch_val)
# --- eof
