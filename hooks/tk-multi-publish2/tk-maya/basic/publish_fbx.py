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
import re
import sgtk
import utils_api3

import maya.cmds as cmds
import maya.mel as mel

from python import util_reference

HookBaseClass = sgtk.get_hook_baseclass()

# Define the fbx version of the export to use
# Note: Two extra zeros are required at the end of the fbx version number..
# More info here: https://docs.unrealengine.com/en-US/WorkingWithContent/Importing/FBX/index.html
FBX_EXPORT_VERSION = 'FBX201800'
PROJ_NAME = os.environ['CURR_PROJECT']
ALLOWED_STEPS_FOR_EXPORT_SELECTED = ['RIG', 'ANIM']
SEARCH_GROUP = ['model', 'structure']
ACCEPTED_ASSET_TYPES = ['Character', 'Prop', 'Environment', 'Pipeline']

class MayaFBXPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open maya session as an exported FBX.

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
        <p>This plugin exports the Asset for the current session as an FBX file.
        The scene will be exported to the path defined by this plugin's configured
        "Publish Template" setting.  The resulting FBX file can then be imported
        into Unreal Engine via the Loader.</p>
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
        base_settings = super(MayaFBXPublishPlugin, self).settings or {}

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
        accept() method. Strings can contain glob patterns such as *,
        for example ["maya.*", "file.maya"]
        """
        return ["maya.fbx"]

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

        # SSE: we want this off by default when the UI starts, see also return
        # below (DW 2020-08-17)
        checked = False

        # ensure a work file template is available on the parent item
        work_template = item.parent.properties.get("work_template")
        if not work_template:
            self.logger.debug(
                "A work template is required for the session item in order to "
                "publish an FBX file. Not accepting FBX item."
            )
            accepted = False

        # ensure the publish template is defined and valid and that we also have
        publish_template = publisher.get_template_by_name(template_name)
        if not publish_template:
            self.logger.debug(
                "The valid publish template could not be determined for the "
                "FBX item. Not accepting the item."
            )
            accepted = False

        # we've validated the publish template. add it to the item properties
        # for use in subsequent methods
        item.properties["publish_template"] = publish_template

        # because a publish template is configured, disable context change. This
        # is a temporary measure until the publisher handles context switching
        # natively.
        item.context_change_allowed = False

        path = _session_path()
        work_template = item.parent.properties.get("work_template")
        work_fields = work_template.get_fields(path)
        if 'ANIM' in work_fields['Step']:
            # Let's uncheck the default fbx export item for the entire scene.
            # We want to export individual assets instead.
            if item.properties.get("file_path") is None:
                checked = False
            else:
                # In an ANIM shot check everything else that is accepted
                checked = True

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

        # create the publish path by applying the fields. store it in the item's
        # properties. This is the path we'll create and then publish in the base
        # publish plugin. Also set the publish_path to be explicit.
        item.properties["path"] = publish_template.apply_fields(work_fields)
        item.properties["publish_path"] = item.properties["path"]
        item.properties["publish_type"] = "Maya FBX"

        # use the work file's version number when publishing
        if "version" in work_fields:
            item.properties["publish_version"] = work_fields["version"]

        # Bake the pipeline step into item properties to check if we need to
        # FBXExportBakeComplexAnimation during export or not.
        item.properties['current_step'] = work_fields['Step']
        try:
            self.get_master_group_node(item, step=work_fields['Step'])
        except Exception as e:
            self.logger.debug(e)

        # Set the fbx export flag to "Export all" by default
        item.properties['select_flag'] = ''

        # In an Unreal pipeline based projects, we want
        # to use `fbx export selected` for steps: RIG and ANIM by default.
        item.properties['project_name'] = PROJ_NAME
        if 'RIG' in work_fields['Step'] and \
                work_fields['Step'] in ALLOWED_STEPS_FOR_EXPORT_SELECTED:
            self.validate_rigs_for_ue(item, work_fields)

        if 'ANIM' in work_fields['Step']:
            if work_fields['Step'] in ALLOWED_STEPS_FOR_EXPORT_SELECTED:
                valid_refs = self.validate_references_for_ue(item)
                if not valid_refs:
                    return False
            else:
                # The default behaviour is to "export all" which works as
                # intended in a MOD/RIG context. In an ANIM context it does not.
                # The expectation is that only the published item selected (the
                # referenced asset), will be exported - not the entire scene.
                valid_refs = self.validate_references(item)
                if not valid_refs:
                    return False

        # --- For debugging contents of item ---
        self.logger.debug('== Item properties ==')
        for key, val in item.properties.items():
            self.logger.debug('{} => {}'.format(key, val))

        # run the base class validation
        return super(MayaFBXPublishPlugin, self).validate(settings, item)

    def validate_rigs(self, item, work_fields):
        """
        Validate asset in RIG step.

        :param item: Item to process
        :param work_fields: The work fields dict associated with the file
        """
        if not work_fields:
            self.logger.warning(
                'Workfields data is required! {} given'.format(work_fields)
            )
        item.properties['asset_type'] = work_fields['sg_asset_type']

        self.get_master_group_node(item)

        # Use the work_fields info to grab the name of the asset
        item.properties['fbx_name'] = work_fields['Asset']

        self.validate_export_groups(item, [item.properties['master_group']])

    def validate_references(self, item):
        """
        Validate referenced assets.

        :param item: Item to process
        :return: True if all validation passes. False otherwise.
        """
        sg_inst = utils_api3.ShotgunApi3()
        self.get_asset_type(item, sg_inst)

        self.check_reference_number(item)

        # Let's bake the name of the asset in the output fbx by
        # inserting the name into the "publish_path" file path.
        if item.properties.get("asset_type"):
            self.tweak_fbx_base_name(item, sg_inst)

        # Populate the "Upstream Published Files" field for the published FBX
        self.set_upstream_published_files(item)

        # Set the export groups property
        valid_groups = self.validate_export_groups(
            item,
            [item.properties['master_group']]
        )

        if valid_groups:
            item.properties['select_flag'] = '-s'
            return True
        else:
            return False

    def validate_rigs_for_ue(self, item, work_fields):
        """
        Validate rigs for an unreal pipeline project.

        The main difference here is which groups we are targeting for export.
        :param item: Item to process
        :param work_fields: The work fields dict associated with the file
        """
        # Run default rig validation first
        self.validate_rigs(item, work_fields)

        export_grps = [
            self.get_export_group(item, group) for group in SEARCH_GROUP
        ]
        valid_groups = self.validate_export_groups(item, export_grps)

        if valid_groups:
            item.properties['select_flag'] = '-s'
            return True
        else:
            return False

    def validate_references_for_ue(self, item):
        """
        Validate referenced assets for an unreal pipeline project.

        :param item: Item to process
        :return: True if all validation passes. False otherwise.
        """
        # Run default validation first
        self.validate_references(item)

        obj_type = item.properties.get("asset_type")

        if not obj_type in ACCEPTED_ASSET_TYPES:
            # We don't want to allow publishing of any other types except
            # the ones in the list
            self.logger.debug('Invalid asset type => {}'.format(obj_type))
            return False

        if "Pipeline" in obj_type:
            for cam_shape in cmds.ls(type="camera"):
                if "TRACKCAM" in cam_shape:
                    self.logger.debug('Referenced camera detected!')
                    item.properties["export_groups"] = [cam_shape]

        elif "Environment" in obj_type:
            # TODO: Make this more granular and require a "model" group
            #   to exist in the hierarchy?
            item.properties["export_groups"] = [item.properties['master_group']]

        else:
            # TODO: Use a dict of which groups to export given the pipe step?
            #   i.e. {'ANIM': ['model', 'structure'], 'MOD': ['master']}
            export_grps = [
                self.get_export_group(item, group) for group in SEARCH_GROUP
            ]
            valid_export_groups = self.validate_export_groups(item, export_grps)
            if not valid_export_groups:
                msg = 'Please check that the asset contains the following'
                msg += ' group(s) underneath the master group! {}'.format(
                    SEARCH_GROUP
                )
                self.logger.warning(msg)
                return False
        return True

    def check_reference_number(self, item):
        """
        Check for multiple references of the same asset and store which number
        it is.

        :param item: Item to process
        """
        # If there are multiple references of the same asset in the scene,
        # let's add this detail in the name of the fbx.
        # i.e. Prop_RIG, Prop_RIG1, etc.
        try:
            obj_instance = re.findall(
                r"(?<=_RIGRN)\w+",
                item.properties.get('node_name')
            )
            # Note: obj_instance is mainly for debugging that we have the
            # correct information when tweaking the fbx name.
            item.properties['obj_instance'] = "".join(obj_instance)
            item.properties['fbx_name'] = '{}{}'.format(
                item.properties.get("asset_name"),
                item.properties.get("obj_instance")
            )
        except:
            # We don't do anything else if there's only one reference
            item.properties['fbx_name'] = item.properties.get('asset_name')

    def set_upstream_published_files(self, item):
        """
        Add dependencies for the base class to register when publishing by
        linking the fbx to the source published shotgun asset.

        :param item: Item to process
        """
        # Note: In order for the "Upstream Published Files" field to be filled
        # with the proper information, the file path fed into this property
        # NEEDS to exist in the same project. In other words, assets referenced
        # from *another project* will result in this field being empty.
        asset_publish_path = [cmds.referenceQuery(
            item.properties["node_name"],
            filename=True,
            wcn=True
        )]
        if not PROJ_NAME in asset_publish_path[0] and \
                "Pipeline" not in item.properties['asset_type']:
            msg = '{} is sourced from another project!'.format(
                asset_publish_path
            )
            self.logger.warning(msg)
            cmds.warning(msg)

        item.properties["publish_dependencies"] = asset_publish_path

    def validate_export_groups(self, item, export_group_list):
        """
        Ensure we have a list with no None values prior to exporting.

        :param item: Item to process
        :param export_group_list: List of of groups to export
        :return: False if None value is found in the export group list.
                 True otherwise.
        """
        # Sanity check that the list does not contain any None values.
        # If there is, this means that the asset doesn't have the
        # proper naming convention/hierarchy...
        if not None in export_group_list:
            item.properties['export_groups'] = export_group_list
            return True
        else:
            if 'TRACKCAM' not in item.properties['asset_name']:
                msg = 'Could not find all groups to export!'
                self.logger.warning('{} => {}'.format(msg, export_group_list))
                cmds.warning(msg)
                return False

    def get_master_group_node(self, item, step=None):
        """
        Grab the name of the master group.

        :param item: Item to process
        :param step: The current pipeline step
        """
        if step:
            if 'ANIM' in step:
                # Feed in the the master group node of the reference obj.
                # i.e. Character_RIG:master or Prop_RIG:master
                obj_nodes = cmds.referenceQuery(
                    item.properties['node_name'], nodes=True
                )
                for node in obj_nodes:
                    # We only want to target the `master` group.
                    if "master" in node:
                        item.properties['master_group'] = node
                        break
                    else:
                        item.properties['master_group'] = None
        else:
            item.properties['master_group'] = cmds.ls('master')

        if not item.properties['master_group']:
            raise Exception('Unable to find master group for node: {}'.format(
                item.properties['node_name'])
            )

    def get_export_group(self, item, group_to_search):
        """
        Convenience function to grab the 'root' group - that is
        the group we care about exporting within the hierarchy.

        :param item: Item to process.
        :param group_to_search: The search string for the group we want.
        :return: The full string name of the group. None otherwise.
        """
        group_to_select = None
        sub_groups = cmds.listRelatives(
            item.properties.get('master_group'),
            allDescendents=True
        )

        for group in sub_groups:
            if group_to_search in group:
                group_to_select = group
                break

        return group_to_select

    def get_asset_type(self, item, shotgun_instance):
        """
        Given a list of valid asset types, find out what type the item is.

        :param shotgun_instance: Shotgun instance to query data from
        :param item: Item to process
        :return: The shotgun asset type string
        """
        # Set an initial value first
        asset_type = None
        item.properties["asset_type"] = None

        # Handle default fbx item that is always present during a publish;
        # that is the fbx representation of the maya file itself.
        if not item.properties.get("file_path"):
            return

        project = util_reference.get_project(util_reference.get_current_shot())
        valid_asset_types = shotgun_instance.get_valid_asset_types(project)

        # Let's add the asset type to the properties
        for asset_type in valid_asset_types:
            if asset_type in item.properties.get("file_path"):
                item.properties["asset_type"] = asset_type
                break

        return asset_type

    def tweak_fbx_base_name(self, item, shotgun_instance):
        """
        Tweak the fbx file name from default (which is the name of the
        maya file) to the name of the asset. This is primarily within an ANIM
        shot.

        :param shotgun_instance: Shotgun instance to query data from
        :param item: Item to process
        """
        orig_name = os.path.basename(item.properties.get("publish_path"))

        step =  util_reference.get_step(util_reference.get_current_shot())
        delimiter = shotgun_instance.get_project_entity_name_delimiter(
            my_proj=PROJ_NAME
        )
        formatted_name = '{0}{1}{0}{2}'.format(
            delimiter,
            item.properties.get("fbx_name"),
            step
        )
        new_name = orig_name.replace(
            '{0}{1}'.format(delimiter, step),
            formatted_name
        )
        new_fbx_path = os.path.join(
            os.path.dirname(item.properties.get("publish_path")),
            new_name
        )
        item.properties['publish_path'] = new_fbx_path
        item.properties['path'] = new_fbx_path

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        self.logger.debug('Attempting to publish => {}'.format(
            item.properties.get('path'))
        )
        publisher = self.parent

        # get the path to create and publish
        publish_path = item.properties["path"]

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # Let's select the group(s) we want to export
        cmds.select(clear=True)
        export_animation = False
        embed_media = False
        current_step = item.properties.get('current_step')
        try:
            if current_step in ALLOWED_STEPS_FOR_EXPORT_SELECTED:
                for group in item.properties.get('export_groups'):
                    cmds.select(group, add=True)
                if 'ANIM' in current_step:
                    export_animation = True
                    # embed_media = True  # TODO: Enable this in ANIM step?
                if 'RIG' in current_step:
                    embed_media = True

        except Exception as e:
            # Handle a default fbx publish
            self.logger.warning(
                'Failed to select export group(s) {}'.format(e)
            )
            self.logger.debug('Running vanilla fbx export')

        # Run the export
        self.export_fbx([
            publish_path,
            item.properties.get('select_flag'),
            export_animation,
            embed_media,
            FBX_EXPORT_VERSION,
        ])

        cmds.select(clear=True)

        self.logger.debug('Publishing FBX to Shotgun')
        # Publish the fbx to Shotgun
        super(MayaFBXPublishPlugin, self).publish(settings, item)

    def export_fbx(self, fbx_args):
        """
        Export to FBX given a list of arguments.

        :param fbx_args: The list of arguments for fbx command to execute
        :return: True if successful, False otherwise.
        """
        selected_groups = cmds.ls(sl=True)
        if selected_groups:
            self.logger.debug('Exporting => {}'.format(selected_groups))
        else:
            self.logger.debug('Exporting all')

        try:
            cmds.FBXResetExport()

            # Extra checkboxes to set prior to export
            cmds.FBXExportSmoothingGroups('-v', True)
            cmds.FBXExportTangents('-v', True)
            cmds.FBXExportSmoothMesh('-v', True)
            cmds.FBXExportReferencedAssetsContent('-v', True)
            cmds.FBXExportBakeComplexAnimation('-v', fbx_args[2])
            cmds.FBXExportEmbeddedTextures('-v', fbx_args[3])
            cmds.FBXExportFileVersion('-v', FBX_EXPORT_VERSION)

            cmds.FBXExportGenerateLog('-v', False)
            self.logger.debug('FBX args => {}'.format(fbx_args))
            self.logger.debug("cmds.FBXExport('-f', {0}, {1})".format(
                fbx_args[0], fbx_args[1]
            ))
            cmds.FBXExport('-f', fbx_args[0], fbx_args[1])

        except Exception as e:
            self.logger.error(
                "Could not export {} to FBX. {}".format(selected_groups, e)
            )
            return False

        return True

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
