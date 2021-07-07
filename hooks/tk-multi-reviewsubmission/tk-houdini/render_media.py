# SSE: Modified to encompass the outside-vendor-provided
# tk-maya-playblast app functionailty, which we had also customized to fit
# our requirements.
# linter: flake8
# docstring style: Google
# (@CH 2021-05-26)

import sgtk
import tempfile
import hou
import os
import re


HookBaseClass = sgtk.get_hook_baseclass()

# global variables
CAMERA_NAME_PATTERN = r'\w+:TRACKCAMShape'
CURR_PROJECT = os.environ['CURR_PROJECT']
DEFAULT_HEIGHT = 720
DEFAULT_WIDTH = 1280
FLIPBOOK_WINDOW = 'Flipbook_Window'
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

FLIPBOOK_PARAMS = {
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
    RenderMedia hook implementation for the tk-houdini engine.
    """
    def __init__(self, *args, **kwargs):
        super(RenderMedia, self).__init__(*args, **kwargs)

        self.__app = self.parent
        self.app = self.__app

    def get_default_flipbook_args(self, output_path):
        """Returns a dictionary of flipbook arguments key/value pairs, using
        values that are specific to SSE's requirements, e.g. H.264, never use
        '.iff' sequences, etcetera.

        update to Houdini flipbook settings doc link below:

        For more information about the playblast API:
        https://help.autodesk.com/view/MAYAUL/2020/ENU/...
                                       ...?guid=__CommandsPython_playblast_html

        For more information: about the doPlayblastArgList mel function, look
        at the doPlayblastArgList.mel in the Autodesk Maya app bundle.

        Args:
            output_path (str): Path to the output movie that will be
            rendered.

        Returns:
            dict: Flipbook arguments.
        """
        flipbook_args = FLIPBOOK_PARAMS
        flipbook_args['filename'] = output_path
        flipbook_args['width'] = DEFAULT_WIDTH
        flipbook_args['height'] = DEFAULT_HEIGHT

        # frame range
        flipbook_args['startTime'] = str(1)

        end_frame = self.get_shot_endframe()
        flipbook_args['endTime'] = str(end_frame)

        # include audio if available
        # update required for houdini/
        # audio_list = pm.ls(type='audio')
        # if audio_list:
        #    flipbook_args['sound'] = audio_list[0]

        return flipbook_args

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
        """
        Render the media

        :param str path:            Path to the input frames for the movie      (Unused)
        :param str output_path:     Path to the output movie that will be rendered
        :param int width:           Width of the output movie                   (Unused)
        :param int height:          Height of the output movie                  (Unused)
        :param int first_frame:     The first frame of the sequence of frames.  (Unused)
        :param int last_frame:      The last frame of the sequence of frames.   (Unused)
        :param int version:         Version number to use for the output movie slate and burn-in
        :param str name:            Name to use in the slate for the output movie
        :param str color_space:     Colorspace of the input frames              (Unused)

        :returns:               Location of the rendered media
        :rtype:                 str
        """
        hou.ui.displayMessage("Implementing render func")
        m = ' >> Rendering media stage initialized...\n{}'.format(
            [input_path, output_path, width, height, first_frame,
                last_frame, version, name, color_space]
        )
        self.logger.info(m)

        fail_head = '>> Failed to create a flipbook'
        
        # debug
        m = '>> Current name {}'.format(
            name
        )
        self.logger.info(m)

        if self.is_valid_shot():
            # name of the flipbook file
            if name == 'Unnamed':
                current_file_path = '{}/{}'.format(
                    hou.expandString("$HIP"),
                    hou.expandString("$HIPNAME")
                )

                if current_file_path:
                    # just the file without the hipname extension
                    name = os.path.basename(current_file_path)
                    name = os.path.splitext(name)[0]
                    name = '{}.mov'.format(name)
                    # debug
                    m = '>> Current name {} for file path {}'.format(
                        name,
                        current_file_path
                    )
                    self.logger.info(m)

            if not output_path:
                output_path = self._get_temp_media_path(name, version, '')
                # debug
                m = '>> NO OUTPUT PATH. ->{}'.format(
                    output_path
                )
                self.logger.info(m)          
            try:
                flipbook_args = self.get_default_flipbook_args(str(output_path))
            except Exception as err:
                m = '>> Flipbook arguments func issues. {}'.format(
                    err
                )
                self.logger.info(m)

            # m = '>> Flipbook arguments > {0} using ({1})'.format(
            #    output_path,
            #    str(flipbook_args)
            # )
            # self.logger.info(m)

            # custom flipbook window
            hou.ui.displayMessage("Custom flipbook window")
        else:
            m = '{}. Not a valid Shot in Project {}.'.format(
                fail_head,
                CURR_PROJECT
            )
            self.logger.info(m)
        #return "N:\\projects\\Magnesium2\\sequences\\MG2RND\\MG2RND_Orbv01\\FX\\work\\claudiohickstein\\houdini\\MG2RND_Orbv01.mp4"
        raise NotImplementedError()

    def pre_render(
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
        """
        Callback executed before the media rendering

        :param str input_path:            Path to the input frames for the movie
        :param str output_path:     Path to the output movie that will be rendered
        :param int width:           Width of the output movie
        :param int height:          Height of the output movie
        :param int first_frame:     The first frame of the sequence of frames.
        :param int last_frame:      The last frame of the sequence of frames.
        :param int version:         Version number to use for the output movie slate and burn-in
        :param str name:            Name to use in the slate for the output movie
        :param str color_space:     Colorspace of the input frames

        :returns:               Location of the rendered media
        :rtype:                 str
        """
        m = ' >> Pre-render stage initialized...\n{}'.format(
            [input_path, output_path, width, height, first_frame,
                last_frame, version, name, color_space]
        )
        self.logger.info(m)
        return "N:\\projects\\Magnesium2\\sequences\\MG2RND\\MG2RND_Orbv01\\FX\\work\\claudiohickstein\\houdini\\MG2RND_Orbv01.mp4"

    def post_render(
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
        """
        Callback executed after the media rendering

        :param str input_path:      Path to the input frames for the movie
        :param str output_path:     Path to the output movie that will be rendered
        :param int width:           Width of the output movie
        :param int height:          Height of the output movie
        :param int first_frame:     The first frame of the sequence of frames.
        :param int last_frame:      The last frame of the sequence of frames.
        :param int version:         Version number to use for the output movie slate and burn-in
        :param str name:            Name to use in the slate for the output movie
        :param str color_space:     Colorspace of the input frames

        :returns:               Location of the rendered media
        :rtype:                 str
        """
        m = ' >> Post-render stage initialized...\n{}'.format(
            [input_path, output_path, width, height, first_frame,
                last_frame, version, name, color_space]
        )
        self.logger.info(m)
        return "N:\\projects\\Magnesium2\\sequences\\MG2RND\\MG2RND_Orbv01\\FX\\work\\claudiohickstein\\houdini\\MG2RND_Orbv01.mp4"

    def _get_temp_media_path(self, name, version, extension):
        """
        Build a temporary path to put the rendered media.

        :param str name:            Name of the media being rendered
        :param str version:         Version number of the media being rendered
        :param str extension:       Extension of the media being rendered

        :returns:               Temporary path to put the rendered version
        :rtype:                 str
        """
        # name = name or ""

        # if version:
        #    suffix = "_v" + version + extension
        # else:
        #    suffix = extension

        # with tempfile.NamedTemporaryFile(prefix=name + "-", suffix=suffix) as \
        #        temp_file:
        #    return temp_file.name

        temp_dir = tempfile.gettempdir()
        temp_media_path = '{0}\\{1}'.format(temp_dir, name)

        hou.ui.displayMessage(temp_media_path)

        return temp_media_path


    def is_valid_shot(self):
        """Check to see if the open Houdini file is from a valid Shot file.

        Returns:
            bool: True if the open Houdini file is from a Shotgun Toolkit
             Primary storage location, otherwise False.
        """
        valid_shot = False
        primary_dir = 'N:/projects/{}/sequences'.format(CURR_PROJECT)

        houdini_file = hou.expandString("$HIP")
        file_parts = houdini_file.split('/')
        if os.path.exists(houdini_file) and len(file_parts) == 10:
            sub_dirs = '/'.join(file_parts[4:9])
            chk_dir = '{0}/{1}'.format(primary_dir, sub_dirs)

            if houdini_file.startswith(chk_dir):
                valid_shot = True
                # debug
                m = ">> Valid shot found at {}".format(
                    houdini_file
                )
                self.logger.info(m)
        return valid_shot

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
                if isinstance(end_frame, int):
                    end_frame = end_frame_chk

                    m = '>> Shotgun end frame for {0} > {1}'.format(
                        shot_name,
                        end_frame
                    )
                    self.logger.info(m)

    def destroy_window(self):
        """If the FLIPBOOK_WINDOWS exists, destroy it (window and its prefs).
        """
        hou.ui.displayMessage("destroy_window")
        pass

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

    def set_camera(self):
        """Find first camera matching pattern and set as active camera, also
        record the original overscan then set the required overscan.

        Not sure why we need overscan feature but we will maintain
        the pattern for Houdini. @CH

        Returns:
            bool: Success at finding the TRACKCAM and recording its original
                overscan value.
        """
        success = False

        # @CH test implementation
        return True

        # re-factoring below for Houdini

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
            mb_title = 'Cannot Flipbook version to Shotgun'
            m = 'A referenced TRACKCAM is required for Shotgun playblasts.'
            hou.ui.displayMessage(m, title=mb_title)
            success = False

        return success

        

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
        pass
# eof
