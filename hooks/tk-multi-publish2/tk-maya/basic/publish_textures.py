# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import json
import os
import maya.cmds as cmds
import maya.mel as mel
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class MayaTexturesPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open maya session's textures.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_session.py"

    """

    # NOTE: The plugin icon and name are defined by the base file plugin.

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        return """
        <p>This plugin publishes session textures. The plugin will fail to
        validate if there are no textures found.</p>
        """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # inherit the settings from the base publish plugin
        base_settings = super(MayaTexturesPublishPlugin, self).settings or {}

        # settings specific to this class
        maya_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                               "correspond to a template defined in "
                               "templates.yml.",
            }
        }

        base_settings.update(maya_publish_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for
        example ["maya.*", "file.maya"]
        """
        return ["maya.textures"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via
        the item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are
            `Setting` instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        accepted = True
        publisher = self.parent
        template_name = settings["Publish Template"].value

        # SSE: we want this ON by default when the UI starts, see also return
        # below (DW 2020-09-18)
        checked = True
        enabled = False

        # SSE: check that there are texture files in the Maya session
        # (DW 2020-09-18)
        f_textures = cmds.ls(textures=True)
        if not f_textures:
            self.logger.debug(
                "Item not accepted because there are no textures in the Maya "
                "session!"
            )
            accepted = False

        # ensure a work file template is available on the parent item
        work_template = item.parent.properties.get("work_template")
        if not work_template:
            self.logger.debug(
                "A work template is required for the session item in order to "
                "publish texture files. Not accepting textures item."
            )
            accepted = False

        # ensure the publish template is defined and valid and that we also
        # have
        publish_template = publisher.get_template_by_name(template_name)
        if not publish_template:
            self.logger.debug(
                "The valid publish template could not be determined for the "
                "textures item. Not accepting the item."
            )
            accepted = False

        # we've validated the publish template. add it to the item properties
        # for use in subsequent methods
        item.properties["publish_template"] = publish_template

        # because a publish template is configured, disable context change.
        # This is a temporary measure until the publisher handles context
        # switching natively.
        item.context_change_allowed = False

        return {
            "accepted": accepted,
            "checked": checked,
            "enabled": enabled
        }

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are
            `Setting` instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """

        path = _session_path()

        # ensure the session has been saved
        if not path:
            # the session still requires saving. provide a save button.
            # validation fails.
            error_msg = "The Maya session has not been saved."
            self.logger.error(
                error_msg,
                extra=_get_save_as_action()
            )
            raise Exception(error_msg)

        # get the normalized path
        path = sgtk.util.ShotgunPath.normalize(path)

        # SSE: check that there are texture files in the Maya session
        # (DW 2020-09-18)
        t_check = _texture_check()
        if not t_check:
            error_msg = (
                "Validation failed because there are no textures in the "
                "scene. You can uncheck this plugin or create "
                "textures to avoid this error."
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # get the configured work file template
        work_template = item.parent.properties.get("work_template")
        publish_template = item.properties.get("publish_template")

        # get the current scene path and extract fields from it using the work
        # template:
        work_fields = work_template.get_fields(path)

        # ensure the fields work for the publish template
        missing_keys = publish_template.missing_keys(work_fields)
        if missing_keys:
            error_msg = "Work file '%s' missing keys required for the " \
                        "publish template: %s" % (path, missing_keys)
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # create the publish path by applying the fields. store it in the
        # item's properties. This is the path we'll create and then publish in
        # the base publish plugin. Also set the publish_path to be explicit.
        item.properties["path"] = publish_template.apply_fields(work_fields)
        item.properties["publish_path"] = item.properties["path"]
        item.properties["publish_type"] = "Maya textures"

        # use the work file's version number when publishing
        if "version" in work_fields:
            item.properties["publish_version"] = work_fields["version"]

        # run the base class validation
        return super(MayaTexturesPublishPlugin, self).validate(settings, item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are
            `Setting` instances.
        :param item: Item to process

        NOTE: The publish_texture module doesn't actually *do* a SG Publish of
        the textures, it copies textures to directories in the publish Schema,
        so I'm registering the publish using the publish_texture Asset log
        file. (DW 2020-09-21)
        """
        # get the path to create and publish
        publish_path = item.properties["path"]

        # write out the tex_list_file to publish against
        publish_folder = os.path.dirname(publish_path)
        try:
            success = _create_texture_list_on_disk(publish_path)
            self.logger.debug('Created > {}'.format(publish_path))
        except Exception, e:
            self.logger.error("Failed to run publish_texture: %s" % e)
            return

        # Call the pipeline repository python module
        #try:
        #    from python import publish_texture
        #    publish_texture._publish_texture()
        #except Exception, e:
        #    self.logger.error("Failed to run publish_texture: %s" % e)
        #    return

        # standard Publish code
        publisher = self.parent

        # ensure the publish folder exists:
        publisher.ensure_folder_exists(publish_folder)

        # let the base class register the publish
        super(MayaTexturesPublishPlugin, self).publish(settings, item)


def _session_path():
    """
    Return the path to the current session
    :return:
    """
    path = cmds.file(query=True, sn=True)

    if isinstance(path, unicode):
        path = path.encode("utf-8")

    return path


def _save_session(path):
    """
    Save the current session to the supplied path.
    """

    # Maya can choose the wrong file type so we should set it here
    # explicitly based on the extension
    maya_file_type = None
    if path.lower().endswith(".ma"):
        maya_file_type = "mayaAscii"
    elif path.lower().endswith(".mb"):
        maya_file_type = "mayaBinary"

    cmds.file(rename=path)

    # save the scene:
    if maya_file_type:
        cmds.file(save=True, force=True, type=maya_file_type)
    else:
        cmds.file(save=True, force=True)


# TODO: method duplicated in all the maya hooks
def _get_save_as_action():
    """
    Simple helper for returning a log action dict for saving the session
    """

    engine = sgtk.platform.current_engine()

    # default save callback
    callback = cmds.SaveScene

    # if workfiles2 is configured, use that for file save
    if "tk-multi-workfiles2" in engine.apps:
        app = engine.apps["tk-multi-workfiles2"]
        if hasattr(app, "show_file_save_dlg"):
            callback = app.show_file_save_dlg

    return {
        "action_button": {
            "label": "Save As...",
            "tooltip": "Save the current session",
            "callback": callback
        }
    }


#  more SSE (DW 2020-09-21)
def _texture_check():
    """Inspect the current session Maya file for textures of all sorts, return
    whether any were discovered or not.

    Returns:
        bool: True if textures are discovered, otherwise False.
    """
    result = False
    f_textures = _get_texture_list()
    if f_textures:
        result = True

    return result


def _get_texture_list():
    """Inspect the current session Maya file for textures of all sorts, return
    whatever is found (either a populated or empty list of texture data path
    dictionaries).

    Returns:
        list: A list of texture data path dictionaries.
    """
    f_textures = []

    # Get scene textures
    tex_nodes = cmds.ls(textures=True)
    if tex_nodes:
        for tex_node in tex_nodes:
            # vanilla Maya
            if cmds.nodeType(tex_node) == 'file':
                tex_path = cmds.getAttr('{}.fileTextureName'.format(tex_node))
                if tex_path:
                    tex_dict = {}
                    tex_dict['node_name'] = tex_node
                    tex_dict['node_type'] = ['Maya', 'file']
                    tex_dict['file_path'] = tex_path
                    f_textures.append(tex_dict)

            # Arnold
            if cmds.nodeType(tex_node) == 'aiImage':
                tex_path = cmds.getAttr('{}.filename'.format(tex_node))
                if tex_path:
                    tex_dict = {}
                    tex_dict['node_name'] = tex_node
                    tex_dict['node_type'] = ['MtoA', 'aiImage']
                    tex_dict['file_path'] = tex_path
                    f_textures.append(tex_dict)

    # Yeti has its own texture nodes that need to be considered, that the 'ls'
    # command doesn't recognize, so...
    ynodes = cmds.ls(type='pgYetiMaya')
    if ynodes:
        for ynode in ynodes:
            mel_cmd = 'pgYetiGraph -listNodes -type "texture" {}'.format(ynode)
            y_tex_nodes = mel.eval(mel_cmd)
            if y_tex_nodes:
                for y_tex_node in y_tex_nodes:
                    mel_bits = []
                    mel_bits.append('pgYetiGraph')
                    mel_bits.append('-node {}'.format(y_tex_node))
                    mel_bits.append('-param "file_name"')
                    mel_bits.append('-getParamValue {}'.format(ynode))
                    _mel_cmd = ' '.join(mel_bits)
                    tex_path = mel.eval(_mel_cmd)

                    tex_dict = {}
                    tex_dict['node_name'] = y_tex_node
                    tex_dict['node_type'] = ['pgYetiMaya', 'texture']
                    tex_dict['file_path'] = tex_path
                    f_textures.append(tex_dict)

    if f_textures:
        f_textures = sorted(f_textures, key=lambda k: k['node_type'][0])

    return f_textures


def _create_texture_list_on_disk(publish_path):
    """Creates a versioned text file in a template.yml specified directory to
    Publish against. File on disk is a json with keys for nodes and their
    related filepaths from the current Maya session.

    Args:
        publish_path (str): [description]

    Returns:
        bool: True if successful, otherwise False.
    """
    success = False

    f_textures = _get_texture_list()
    if f_textures:
        json_root_dict = {}
        json_root_dict['scene_file'] = cmds.file(q=True, sn=True)
        json_root_dict['texture_list'] = f_textures

        json_dir = os.path.dirname(publish_path)
        json_name = os.path.basename(publish_path)
        json_filepath = '{0}/{1}'.format(json_dir, json_name)

        if not os.path.exists(json_dir):
            os.makedirs(json_dir)

        with open(json_filepath, 'w') as write_json:
            json.dump(
                json_root_dict,
                write_json,
                sort_keys=True,
                indent=4,
                separators=(',', ': ')
            )

        if os.path.isfile(json_filepath):
            success = True

    return success
# --- eof
