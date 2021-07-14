# SSE: Modified to replicate our legacy+ Shotgun configuration post_publish
# functionailty, which was customized to fit our requirements.
# linter: flake8
# docstring style: Google
# (DW 2020-08-11)

import json
import os
import sgtk
import shutil

HookBaseClass = sgtk.get_hook_baseclass()

SSE_HEADER = '>> Sinking Ship'


class PostPhaseHook(HookBaseClass):
    """
    This hook defines methods that are executed after each phase of a publish:
    validation, publish, and finalization. Each method receives the publish
    tree instance being used by the publisher, giving full control to further
    curate the publish tree including the publish items and the tasks attached
    to them. See the :class:`PublishTree` documentation for additional details
    on how to traverse the tree and manipulate it.
    """

    # See the developer docs for more information about the methods that can be
    # defined here: https://developer.shotgunsoftware.com/tk-multi-publish2/

    def post_publish(self, publish_tree):
        """This method is executed after the publish pass has completed for
        each item in the tree, before the finalize pass.

        A :ref:`publish-api-tree` instance representing the items that were
        published is supplied as an argument. The tree can be traversed in this
        method to inspect the items and process them collectively.

        To glean information about the publish state of particular items, you
        can iterate over the items in the tree and introspect their
            :py:attr:`~.api.PublishItem.properties` dictionary.
        This requires customizing your publish plugins to populate any specific
        publish information that you want to process collectively here.

        NOTE: You will not be able to use the item's
            :py:attr:`~.api.PublishItem.local_properties` in this hook since
            :py:attr:`~.api.PublishItem.local_properties` are only accessible
        during the execution of a publish plugin.

        Args:
            publish_tree (obj): The :ref:`publish-api-tree` instance
                representing the items to be published.
        """
        m = '{} post_publish'.format(SSE_HEADER)
        self.logger.debug(m)

        # engine
        current_engine = sgtk.platform.current_engine()
        if current_engine.name == 'tk-aftereffects':
            pass
        if current_engine.name == 'tk-houdini':
            pass
        if current_engine.name == 'tk-mari':
            pass
        if current_engine.name == 'tk-maya':
            self.post_publish_maya()
        if current_engine.name == 'tk-nuke':
            pass

    ###########################################################################
    # engine methods                                                          #
    ###########################################################################
    def post_publish_maya(self):
        """Calls the appropriate method to run after a publish depending on
        the Pipeline Step in a session running the Maya engine.
        """
        m = '{} post_publish_maya'.format(SSE_HEADER)
        self.logger.debug(m)

        import utils_api3
        import maya.cmds as cmds

        self.utils_api3 = utils_api3.ShotgunApi3()
        scene_name = cmds.file(q=True, sn=True)

        e_type = self.parent.context.entity['type']
        p_step = self.parent.context.step['name']

        wk_template = self.parent.sgtk.templates.get('maya_asset_work')
        if e_type == 'Asset' and p_step == 'Surfacing':
            wk_template = self.parent.sgtk.templates.get(
                'maya_asset_work_surfacing_arnold'
            )

        if e_type == 'Shot':
            wk_template = self.parent.sgtk.templates.get('maya_shot_work')
        wk_fields = wk_template.get_fields(scene_name)

        # method calls based on Shotgun pipeline steps as defined at SSE
        # NOTE: pipeline steps that call no method are included for possible
        # future use
        if e_type == 'Asset':
            # pipeline steps for Asset, in order
            # (see 'asset methods', below)
            if p_step == 'Modeling':
                self.post_publish_maya_mod(scene_name, wk_fields)
            if p_step == 'Rigging':
                self.post_publish_maya_rig(scene_name, wk_fields)
            if p_step == 'Texturing':  # < NOTE: this step is now deprecated
                pass
            if p_step == 'Surfacing':
                self.post_publish_maya_surf(scene_name, wk_fields)
            if p_step == 'FX':
                self.post_publish_maya_fx_asset(scene_name, wk_fields)

        if e_type == 'Shot':
            # pipeline steps for Shot, in order
            # (see 'shot methods', below)
            if p_step == 'Previz':
                self.post_publish_maya_prvz(scene_name, wk_fields)
            if p_step == 'Tracking & Layout':
                self.post_publish_maya_tlo(scene_name, wk_fields)
            if p_step == 'Animation':
                self.post_publish_maya_anim(scene_name, wk_fields)
            if p_step == 'Character Finaling':
                self.post_publish_maya_cfx(scene_name, wk_fields)
            if p_step == 'FX':
                self.post_publish_maya_fx_shot(scene_name, wk_fields)
            if p_step == 'Lighting':
                pass

    ###########################################################################
    # asset methods - maya                                                    #
    ###########################################################################
    def post_publish_maya_mod(self, scene_name, wk_fields):
        """For the 'Model'/MOD Asset Publishes, based on what Asset Type they
        are, generate a simple autorig via a Deadline process on the render
        farm.

        Args:
            scene_name (str): The full path to the curently open Maya file.
            wk_fields (dict): Fields provided by the Shotgun Toolkit template
                for the Project.
        """
        m = '{} post_publish_maya_mod'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

        # check the entity type against valid types for simple autorigging
        ent_type = wk_fields['sg_asset_type']

        v_types = [
            'Prop',
            'Vehicle'
        ]

        if ent_type in v_types:
            # check for any existing RIG publishes, use our convenience
            # api3 wrapper method (by this point it's in the path)
            prj_name = self.parent.context.project['name']
            ent_name = self.parent.context.entity['name']

            pub_chk = self.utils_api3.get_latest_asset_pub_in_proj_by_step(
                prj_name,
                ent_name,
                e_step='RIG'
            )

            # farm submission for simple autorig job
            if pub_chk:
                # skip
                m = '{0} Skipping simple rig auto-publish, found > {1}'.format(
                    SSE_HEADER,
                    pub_chk
                )
                self.logger.debug(m)
            else:
                # submit the deadline job
                # TODO: try/except
                from python import publish_asset
                reload(publish_asset)
                publish_asset.run_autorig_publish(
                    submit=True,
                    fields=wk_fields
                )

                m = '{} Submitted simple rig auto-publish to Deadline'.format(
                    SSE_HEADER
                )
                self.logger.debug(m)

    def post_publish_maya_rig(self, scene_name, wk_fields):
        """For the 'Rigging'/RIG Asset Publishes, create a 'versionless'
        subdirectory under the standard RIG Publish directory, and put a
        version-stripped copy of the most recent RIG Publish in it (overwrites
        the target).
        NOTE: This is in prep for the idea of a 'versionless' workflow when it
        comes to RIGs in ANIM files, remains here but is on the backburner
        (might suggest it for outsource ANIM).

        Args:
            scene_name (str): The full path to the curently open Maya file.
            wk_fields (dict): Fields provided by the Shotgun Toolkit template
                for the Project.
        """
        m = '{} post_publish_maya_rig'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

        # data for versionless path and file
        asset_data = {}
        asset_data['Step'] = wk_fields['Step']
        asset_data['Asset'] = wk_fields['Asset']
        asset_data['sg_asset_type'] = wk_fields['sg_asset_type']
        asset_data['version'] = wk_fields['version']

        if 'name' in wk_fields.keys():
            asset_data['name'] = wk_fields['name']

        pub_template = self.parent.sgtk.templates.get('maya_asset_publish')
        v_file = pub_template.apply_fields(asset_data)

        v_name = os.path.basename(v_file)
        f_version = v_name.split('.')[-2]
        f_replace = '.{}.'.format(f_version)

        v_file = v_file.replace('\\', '/')
        v_file = v_file.replace('/maya/', '/maya/versionless/')
        v_file = v_file.replace(f_replace, '.')

        # make the destination 'versionless' publish subdirectory
        v_dir = os.path.dirname(v_file)
        if not os.path.exists(v_dir):
            os.makedirs(v_dir)

        # copy!
        self._copy_file(scene_name, v_file)

    def post_publish_maya_surf(self, scene_name, wk_fields):
        """For the 'Surfacing'/SURF Asset Publishes, if in a correctly named
        SUR_AI/SUR.AI file (Maya scene with all geometry and shaders), write
        and publish a SHD_AI/SHD.AI file (Maya scene shaders only), and
        also write (without publishing) a JSON file that describes the source
        Maya file's geometry to shader connections.

        Args:
            scene_name (str): The full path to the curently open Maya file.
            wk_fields (dict): Fields provided by the Shotgun Toolkit template
                for the Project.
        """
        m = '{} post_publish_maya_surf'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

        # get the base name of the file, remove the version and extension,
        # then normalize the delimiter to '_' to check if this is a SUR_AI/
        # SHD.AI source file
        base_name = os.path.basename(scene_name)
        base_parts = base_name.split('.')
        base_ext = base_parts[-1]
        base_vers = base_parts[-2]
        base_repl = '.{0}.{1}'.format(base_vers, base_ext)
        base_no_ve = base_name.replace(base_repl, '')
        base_no_ve_norm = base_no_ve.replace('.', '_')

        sur_filt = '_SUR_AI'

        if base_no_ve_norm.endswith(sur_filt):
            from python.render_engine.arnold import utils_arnold

            utils_arnold.write_geo_shd_json()
            utils_arnold._export_shd_file_from_sur_file()

    def post_publish_maya_fx_asset(self, scene_name, wk_fields):
        m = '{} post_publish_maya_fx_asset'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

    ###########################################################################
    # shot methods - maya                                                     #
    ###########################################################################
    def post_publish_maya_prvz(self, scene_name, wk_fields):
        """Create the 'initial TLO' file when a Previz publish is triggered.
        Uses the 'initial LIGHT' concept as inspiration.

        Args:
            scene_name (str): The full path to the currently open Maya file.
            wk_fields (dict): Fields provided by the Shotgun Toolkit template
                for the Project.
        """
        m = '{} post_publish_maya_prvz'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

        # import & call method
        # TODO: try/except
        from python import publish_previz
        reload(publish_previz)
        publish_previz.create_initial_tlo_file3(scene_name, wk_fields)

    def post_publish_maya_tlo(self, scene_name, wk_fields):
        """Copies the TLO file to a matching ANIM file, in the current Shotgun
        user's work directory for the destination Pipeline Step.
        NOTE: we could potentially have it Publish the ANIM file (an 'initial
        anim file'), but for the short term we'll just mimic the legacy+
        behaviour of a simple file copy.

        Args:
            scene_name (str): The full path to the currently open Maya file.
            wk_fields (dict): Fields provided by the Shotgun Toolkit template
                for the Project.
        """
        m = '{} post_publish_maya_tlo'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

        # data for the target ANIM Shot
        shot_data = {}
        shot_data['Step'] = u'ANIM'
        shot_data['Sequence'] = wk_fields['Sequence']
        shot_data['Shot'] = wk_fields['Shot']
        shot_data['current_user_name'] = wk_fields['current_user_name']
        shot_data['version'] = 1

        if 'name' in wk_fields.keys():
            shot_data['name'] = wk_fields['name']

        # templates
        wk_template = self.parent.sgtk.templates.get('maya_shot_work')
        anim_file = wk_template.apply_fields(shot_data)
        anim_file_dir = os.path.dirname(anim_file)

        # make the destination ANIM user work directory
        if not os.path.exists(anim_file_dir):
            os.makedirs(anim_file_dir)

        # copy!
        self._copy_file(scene_name, anim_file)

    def post_publish_maya_anim(self, scene_name, wk_fields):
        """For the 'Animation'/ANIM Shot Publishes, submit the starting Alembic
        and Yeti caching process as a Deadline Job on the render farm.

        Args:
            scene_name (str): The full path to the currently open Maya file.
            wk_fields (dict): Fields provided by the Shotgun Toolkit template
                for the Project.
        """
        m = '{} post_publish_maya_anim'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

        # submit the deadline job for ANIM
        # TODO: try/except?
        self.logger.debug('Submit the deadline job for ANIM...')
        from python import publish_anim
        reload(publish_anim)
        publish_anim.run_publish(submit=True)

        m = '{} Submitted ABC/Yeti cache Job to Deadline'.format(
            SSE_HEADER
        )
        self.logger.debug(m)

        # create the initial file for CFX
        # TODO: try/except?
        self.logger.debug('Create the "initial" file for CFX')
        from python import publish_cfx
        reload(publish_cfx)
        publish_cfx.create_initial_cfx_file(scene_name)

    def post_publish_maya_cfx(self, scene_name, wk_fields):
        """For the 'Character Finaling'/CFX Shot Publishes, submit the starting
        Alembic and Yeti caching process as a Deadline Job on the render farm.

        Args:
            scene_name (str): The full path to the currently open Maya file.
            wk_fields (dict): Fields provided by the Shotgun Toolkit template
                for the Project.
        """
        m = '{} post_publish_maya_cfx'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

        # submit the deadline job for CFX
        # TODO: try/except?
        from python import publish_cfx
        reload(publish_cfx)
        publish_cfx.run_publish(submit=True)

        m = '{} Submitted ABC/Yeti cache Job to Deadline'.format(
            SSE_HEADER
        )
        self.logger.debug(m)

    def post_publish_maya_fx_shot(self, scene_name, wk_fields):
        """Inspect the Maya scene file for an 'FX' node and related
        'RenderSetup', and export both to the relevant locations if found.

        Args:
            scene_name (str): The full path to the currently open Maya file.
            wk_fields (dict): Fields provided by the Shotgun Toolkit template
                for the Project.
        """
        m = '{} post_publish_maya_fx_shot'.format(SSE_HEADER)
        self.logger.debug(m)

        # incoming fields/values for debug
        self._log_scene(scene_name)
        self._log_fields(wk_fields)

        # module imports
        import maya.cmds as cmds
        import maya.app.renderSetup.model.renderSetup as renderSetup

        # define export paths and filenames
        wk_template = self.parent.sgtk.templates.get('maya_shot_publish')
        export_dir = os.path.dirname(wk_template.apply_fields(wk_fields))
        export_dir = export_dir.replace('\\', '/')
        export_dir = '{}/export'.format(export_dir)

        export_name = 'fxgrp_{}.ma'.format(wk_fields['Shot'])
        export_file = '{0}/{1}'.format(export_dir, export_name)

        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        if os.path.isfile(export_file):
            os.remove(export_file)

        # maya scene components
        ex_success = False
        try:
            cmds.select('FX')
            cmds.file(
                export_file,
                exportSelected=True,
                type='mayaAscii',
                shader=True
            )
            self.logger.debug('FX export > {}'.format(export_file))
            ex_success = True
        except Exception as e:
            self.logger.debug('Failed FX export > {}'.format(str(e)))

        if ex_success and cmds.mayaHasRenderSetup():
            rs_root = export_file.split('/FX/')[0]
            rs_dir = '{}/LIGHT/templates'.format(rs_root)
            rs_name = 'FX_{}.json'.format(wk_fields['Shot'])
            rs_file = '{0}/{1}'.format(rs_dir, rs_name)

            if not os.path.exists(rs_dir):
                os.makedirs(rs_dir)

            with open(rs_file, 'w+') as j_file:
                json.dump(
                    renderSetup.instance().encode(None, includeSceneSettings=False),
                    fp=j_file,
                    indent=2,
                    sort_keys=True
                )

    ###########################################################################
    # generic methods                                                         #
    ###########################################################################
    def _copy_file(self, src, dst):
        """Copy a source file to a destination file.

        Args:
            src (str): The full source filepath.
            dst (str): The full destination filepath.
        """
        try:
            shutil.copy2(src, dst)
            m = '{0} copied file {1} -> {2}'.format(SSE_HEADER, src, dst)
            self.logger.debug(m)
        except Exception as e:
            m = '{0} file copy failed {1} > {2}'.format(
                SSE_HEADER,
                dst,
                str(e)
            )
            self.logger.debug(m)

    def _log_fields(self, wk_fields):
        """Output passed Shotgun template fields/values for the Project to the
        console as a sanity check.

        Args:
            wk_fields (dict): Incoming template fields/values for display.
        """
        m = '{0} wk_fields > {1}'.format(SSE_HEADER, wk_fields)
        self.logger.debug(m)

    def _log_scene(self, scene_name):
        """Output passed Maya scene filepath to the console as a sanity check.

        Args:
            scene_name (str): The full path to the curently open Maya file.
        """
        m = '{0} scene_name > {1}'.format(SSE_HEADER, scene_name)
        self.logger.debug(m)
# --- eof
