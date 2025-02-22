# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import maya.cmds as cmds
import maya.mel as mel
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class MayaGroomPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open maya session as an exported ABC.

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
        <p> This plugin publishes session groom geometry for the current session. Any
        session geometry under the '|master|yeti_gr|fur' hierarchy will be exported
        to the path defined by this plugin's configured "Publish Template"
        setting. The plugin will fail to validate if the "Yeti" plugin is
        not enabled or cannot be found, or if there is no '|master|yeti_gr'
        hierarchy found..</p>
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
        base_settings = super(MayaGroomPublishPlugin, self).settings or {}

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
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """

        return ["maya.groom"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

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
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        accepted = True
        publisher = self.parent
        template_name = settings["Publish Template"].value

        self.logger.info('Template name is: %s', template_name)

        # SSE: we want this off by default when the UI starts, see also return
        # below (DW 2020-07-28)
        checked = True

        # ensure a work file template is available on the parent item
        work_template = item.parent.properties.get("work_template")
        if not work_template:
            self.logger.debug(
                "A work template is required for the session item in order to "
                "publish an ABC file. Not accepting ABC item."
            )
            accepted = False

        # ensure the publish template is defined and valid and that we also have
        publish_template = publisher.get_template_by_name(template_name)
        if not publish_template:
            self.logger.debug(
                "The valid publish template could not be determined for the "
                "ABC item. Not accepting the item."
            )
            accepted = False

        # check that the AbcExport command is available!
        if not mel.eval("exists \"pgYetiCommand\""):
            self.logger.debug(
                "Item not accepted because Yeti 'pgYetiCommand' "
                "is not available. Perhaps the plugin is not enabled?"
            )
            accepted = False

        # we've validated the publish template. add it to the item properties
        # for use in subsequent methods
        item.properties["publish_template"] = publish_template

        # because a publish template is configured, disable context change. This
        # is a temporary measure until the publisher handles context switching
        # natively.
        item.context_change_allowed = False

        return {
            "accepted": accepted,
            "checked": checked
        }

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """

        path = _session_path()

        # ---- ensure the session has been saved

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

        # check that there is still geometry in the scene
        if not cmds.ls(geometry=True, noIntermediate=True):
            error_msg = (
                "Validation failed because there is no geometry in the scene "
                "to be exported. You can uncheck this plugin or create "
                "geometry to export to avoid this error."
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # SSE: check that the |master|pg_yeti hierarchy exists (LO 2021-05-11)
        node_path = '|master|yeti_gr|fur'
        node_name = item.properties['node_name']
        node_long_name = cmds.ls(node_name, long=True)
        if not node_long_name:
            error_msg = "Unable to retrieve full path for %s." % node_name
            self.logger.error(error_msg)
            raise Exception(error_msg)

        node_long_name = node_long_name[0]
        if node_path not in node_long_name:
            error_msg = "%s is outside of %s hierarchy." % (node_name, node_path)
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # SSE: check that the Yeti graph for the node is not empty
        cmd = [
            'pgYetiGraph',
            '-listNodes',
            '"%s"' % node_name
        ]
        cmd_str = " ".join(cmd)

        try:
            nodes = mel.eval(cmd_str)
            if not nodes:
                error_msg = 'The Yeti graph for %s is empty.' % node_name
                self.logger.error(error_msg)
                raise Exception(error_msg)
        except Exception, e:
            raise Exception(e)

        # get the configured work file template
        work_template = item.parent.properties.get("work_template")
        publish_template = item.properties.get("publish_template")

        # get the current scene path and extract fields from it using the work
        # template:
        work_fields = work_template.get_fields(path)

        # simplify the node name to extract description and add to the work fields
        name = '%s' % (node_name.split('_')[-1].split('Shape')[0]).title()
        work_fields['name'] = name

        # ensure the fields work for the publish template
        missing_keys = publish_template.missing_keys(work_fields)
        if missing_keys:
            error_msg = "Work file '%s' missing keys required for the " \
                        "publish template: %s" % (path, missing_keys)
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # create the publish path by applying the fields. store it in the item's
        # properties. This is the path we'll create and then publish in the base
        # publish plugin. Also set the publish_path to be explicit.
        item.properties["path"] = publish_template.apply_fields(work_fields)
        item.properties["publish_path"] = item.properties["path"]
        item.properties["publish_type"] = "Maya ABC"

        # use the work file's version number when publishing
        if "version" in work_fields:
            item.properties["publish_version"] = work_fields["version"]

        # run the base class validation
        return super(MayaGroomPublishPlugin, self).validate(settings, item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        publisher = self.parent
        node = item.properties['node_name']

        # get the path to create and publish
        publish_path = item.properties["path"]

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # consult the Yeti scripting documentation for exporting to Unreal
        # http://documentation.peregrinelabs.com/yeti/scriptingref.html

        # get the Yeti render values (otherwise it defaults to display values)
        r_dens = cmds.getAttr('%s.renderDensity' % node)
        r_length = cmds.getAttr('%s.renderLength' % node)
        r_width = cmds.getAttr('%s.renderWidth' % node)

        # NOTE: we can fork to support exporting in shots by passing in a context in the item properties
        # then getting the frame range for the shot from Shotgun and adding the range as an argument
        # - range {start} {end}

        publish_path = publish_path.replace('\\', '/')
        cmd = [
            'pgYetiCommand',
            '-exportUnrealAbc',
            '"%s"' % publish_path,
            '-alembicDensity %s' % r_dens,
            '-alembicLength %s' % r_length,
            '-alembicWidth %s' % r_width,
        ]

        cmd_str = " ".join(cmd)
        try:
            self.parent.log_debug("Executing command: %s" % cmd)
            # clear selections, select node and run command
            cmds.select(cl=True)
            cmds.select(node)
            mel.eval(cmd_str)
            cmds.select(cl=True)
        except Exception, e:
            self.logger.error("Failed to export Geometry: %s" % e)
            return

        # let the base class register the publish
        super(MayaGroomPublishPlugin, self).publish(settings, item)

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
