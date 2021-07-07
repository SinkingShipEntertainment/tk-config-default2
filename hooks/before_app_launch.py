# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Before App Launch Hook

This hook is executed prior to application launch and is useful if you need
to set environment variables or run scripts as part of the app initialization.
"""

import os
import sys
import tank

# --- get Shotgun Desktop Console logging going...
import sgtk
LOGGER = sgtk.platform.get_logger(__name__)
MY_SEP = ('=' * 10)

# --- global variables...
OCIO_CONFIG = 'X:/tools/aces/aces_1.0.3/config.ocio'


class BeforeAppLaunch(tank.Hook):
    """
    Hook to set up the system prior to app launch.
    """

    def execute(self, app_path, app_args, version, engine_name, **kwargs):
        """
        The execute functon of the hook will be called prior to starting the
        required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in
            the "versions" settings of the Launcher instance, otherwise None
        :param engine_name (str) The name of the engine associated with the
            software about to be launched.

        """
        # accessing the current context (current shot, etc)
        # can be done via the parent object
        #
        # > multi_launchapp = self.parent
        # > current_entity = multi_launchapp.context.entity
        #
        # you can set environment variables like this:
        # os.environ["MY_SETTING"] = "foo bar"

        # Log args
        LOGGER.debug('app_path    > {}'.format(app_path))
        LOGGER.debug('app_args    > {}'.format(app_args))
        LOGGER.debug('version     > {}'.format(version))
        LOGGER.debug('engine_name > {}'.format(engine_name))
        LOGGER.debug('kwargs      > {}'.format(kwargs))

        # --- This legacy path keeps kicking around, need to determine if it's
        # --- necessary any longer...
        os.environ["XBMLANGPATH"] = "X:\\tools\\release\\icons"

        # --- SG supplied ENVIRONMENT VARIABLES...
        os.environ['SG_APP_VERSION'] = '{}'.format(version)

        multi_launchapp = self.parent
        ml_context = multi_launchapp.context
        os.environ['SG_CURR_ENTITY'] = '{}'.format(ml_context.entity)
        os.environ['SG_CURR_STEP'] = '{}'.format(ml_context.step)
        os.environ['SG_CURR_TASK'] = '{}'.format(ml_context.task)
        os.environ['SG_CURR_PROJECT'] = '{}'.format(ml_context.project)
        os.environ['SG_CURR_LOCATIONS'] = '{}'.format(
            ml_context.filesystem_locations
        )

        # --- get the correct studio tools in the paths (SYS & PYTHONPATH)...
        os.environ['CURR_PROJECT'] = '{}'.format(ml_context.project['name'])
        project_name = os.environ['CURR_PROJECT']

        # --- Set instance variables...
        self._version = version
        self._engine_name = engine_name
        self._shotgun_inst = sgtk.api.shotgun.connection.get_sg_connection()

        # --- Unified studio tools pathing:
        # --- one variable for when we want the fallback effect...
        self._repo_paths = self._return_repo_paths(project_name)
        # --- and another for when we just want the highest-level in
        # --- in the returned repo paths "hierarchy"...
        self._repo_path = self._repo_paths[0]

        # --- OS plug-in component root location (just Windows for now)...
        if sys.platform == 'win32':
            self._wpf_root = 'C:{}Program Files'.format(os.sep)

        # --- Make the SSE Shotgun API available...
        # --- one variable for when we want the fallback effect...
        self._sg_a3_paths = []
        for rp in self._repo_paths:
            self._sg_a3_paths.append('{}/shotgun/api3'.format(rp))
        # --- and another for when we just want the highest-level in
        # --- in the returned repo paths "hierarchy"...
        self._sg_a3_path = self._sg_a3_paths[0]

        # --- Call methods based on the Toolkit engine we're invoking
        # --- (e.g. Maya > 'tk-maya', Nuke > 'tk-nuke', etc.)...
        if engine_name == 'tk-maya':
            self._tk_maya_env_setup()

        if engine_name == 'tk-nuke':
            self._tk_nuke_env_setup()

        if engine_name == 'tk-aftereffects':
            self._tk_aftereffects_env_setup()

        if engine_name == 'tk-houdini':
            self._tk_houdini_env_setup()

        if engine_name == 'tk-natron':
            self._tk_natron_env_setup()

        if engine_name == 'tk-unreal':
            self._tk_unreal_env_setup()

    def return_proj_short_name(self, project_name):
        """Return the Project short name from a Shotgun DB query based on the
        Project's full name.

        Args:
            project_name (str): The Project's full name in Shotgun.

        Returns:
            str: The Project's short name.
        """
        sg_filters = [
            ['name', 'is', project_name]
        ]

        try:
            sg_fields = sorted(
                self._shotgun_inst.schema_read()['Project'].keys()
            )

            f_proj = self._shotgun_inst.find_one(
                'Project',
                sg_filters,
                sg_fields
            )
        except Exception:
            # --- In case of method call outside of subclass instantiation
            # --- on farm...
            shotgun_inst = sgtk.api.shotgun.connection.get_sg_connection()
            sg_fields = sorted(shotgun_inst.schema_read()['Project'].keys())
            f_proj = shotgun_inst.find_one('Project', sg_filters, sg_fields)

        proj_short_name = f_proj['sg_short_name']

        return proj_short_name

    def return_sgtk_configs(self, project_name):
        """Return a list of Shotgun Toolkit configuration dictionaries related
        to the Project name.

        Args:
            project_name (str): The Project's full name in Shotgun.

        Returns:
            list: Discovered Shotgun Toolkit configurations.
        """
        sg_filters = [
            ['project.Project.name', 'is', project_name]
        ]

        sg_fields = [
            'id',
            'code',
            'project',
            'sg_ss_tools_repo',
            'sg_ss_tools_repo_custom_path',
            'windows_path'
        ]

        try:
            sgtk_configs = self._shotgun_inst.find(
                'PipelineConfiguration',
                sg_filters,
                sg_fields
            )
        except Exception:
            # --- In case of method call outside of subclass instantiation
            # --- on farm...
            shotgun_inst = sgtk.api.shotgun.connection.get_sg_connection()
            sgtk_configs = shotgun_inst.find(
                'PipelineConfiguration',
                sg_filters,
                sg_fields
            )

        return sgtk_configs

    def return_wanted_repo_key(self, sgtk_configs):
        """Returns the wanted repo key based on the current SGTK session, as
        well as any related custom path if present.

        Args:
            sgtk_configs (list): a list of Shotgun Toolkit configuration
                dictionaries

        Returns:
            str, str: The wanted repo key for the configuration and the related
                custom repo path (None if there isn't one).
        """
        wanted_repo_key = None
        my_config_repo_custom = None

        sgtk_module_path = sgtk.get_sgtk_module_path()
        sgtk_module_path = sgtk_module_path.replace('\\', '/')
        sgtk_cfg_path = '/'.join(sgtk_module_path.split('/')[:5])

        for my_config in sgtk_configs:
            my_config_repo_key = my_config['sg_ss_tools_repo']
            my_config_repo_custom = my_config['sg_ss_tools_repo_custom_path']

            my_config_path = my_config['windows_path']
            my_config_path = my_config_path.replace('\\', '/')
            if my_config_path == sgtk_cfg_path:
                wanted_repo_key = my_config_repo_key
                m = 'wanted_repo_key >> {}'.format(wanted_repo_key)
                LOGGER.debug(m)
                break

        return wanted_repo_key, my_config_repo_custom

    def return_spr_path(self):
        """A single custom non-project entity exists to provide a central
        Shotgun-centric location to store data about the latest pipeline code
        repository location on disk; this method queries it for the path.

        Returns:
            str: The pipeline code repository root path, or None.
        """
        spr_path = None

        custom_ent = 'CustomNonProjectEntity04'

        my_filters = [
            ['code', 'is', 'studio_pipeline'],
            ['id', 'is', 1],
            ['sg_status_list', 'is', 'cmpt']
        ]

        try:
            my_fields = sorted(
                self._shotgun_inst.schema_read()[custom_ent].keys()
            )

            my_spr_data = self._shotgun_inst.find_one(
                custom_ent,
                my_filters,
                my_fields
            )
        except Exception:
            # --- In case of method call outside of subclass instantiation
            # --- on farm...
            shotgun_inst = sgtk.api.shotgun.connection.get_sg_connection()
            my_fields = sorted(shotgun_inst.schema_read()[custom_ent].keys())

            my_spr_data = shotgun_inst.find_one(
                custom_ent,
                my_filters,
                my_fields
            )

        if my_spr_data:
            repo_root = my_spr_data['sg_repo_root_path']
            major_v = my_spr_data['sg_repo_major_version']
            minor_v = my_spr_data['sg_repo_minor_version']

            # replace the keys in the path with the appropriate
            # numbers...
            spr_path = repo_root.replace('{MAJ}', str(major_v))
            spr_path = spr_path.replace('{MIN}', str(minor_v))
            spr_path = spr_path.replace('\\', '/')

        return spr_path

    def _return_repo_path(self, project_name):
        """Use Shotgun (Toolkit and Database) to get data and return the
        correct code repo root path (singular, first wanted) for the Project
        that Toolkit launched.

        Args:
            project_name (str): The Project's full name in Shotgun.

        Returns:
            str: The root of the path based on information gleaned from
                Shotgun.
        """
        repo_path = None

        repo_paths = self._return_repo_paths(project_name)
        repo_path = repo_paths[0]

        return repo_path

    def _return_repo_paths(self, project_name):
        """Use Shotgun (Toolkit and Database) to get data and return the
        correct code repo root paths for the Project that Toolkit launched.

        Args:
            project_name (str): The Project's full name in Shotgun.

        Returns:
            list:  The roots of the repo paths based on information gleaned
                from Shotgun.
        """
        repo_paths = []

        sg_auth = sgtk.get_authenticated_user()
        sgtk_core_user = sg_auth.login

        spr_path = self.return_spr_path()
        spr_split = os.path.basename(spr_path).split('_')
        v_maj = spr_split[2]
        v_min = spr_split[3]

        # --- Get the Project short name...
        proj_short_name = self.return_proj_short_name(project_name)

        # --- Get the SG configs...
        sgtk_configs = self.return_sgtk_configs(project_name)
        wanted_repo_key, my_config_repo_custom = self.return_wanted_repo_key(
            sgtk_configs
        )

        # --- First check ('custom')...
        if wanted_repo_key == 'custom':
            if my_config_repo_custom:
                if os.path.exists(my_config_repo_custom):
                    repo_path = my_config_repo_custom.replace(
                        '\\', '/'
                    )
                    repo_path = repo_path.strip('/')
                    if os.path.exists(repo_path):
                        repo_paths.append(repo_path)

        # --- Second check ('dev')...
        if wanted_repo_key == 'dev':
            # --- For developers to do individual tesing against clones of
            # --- same-named repositories within their X:/dev location...
            repo_path = 'X:/dev/ss_dev_{}'.format(sgtk_core_user)
            repo_path += '/{0}_pipeline_{1}_{2}_dev_master_repo'.format(
                proj_short_name,
                v_maj,
                v_min
            )
            # --- If it's not a Project-specific repo, we have to resort
            # --- to the generic studio repo dev clone...
            if not os.path.exists(repo_path):
                spr_base = os.path.basename(spr_path)

                repo_path = 'X:/dev/ss_dev_{0}/{1}'.format(
                    sgtk_core_user,
                    spr_base
                )

            if os.path.exists(repo_path):
                repo_paths.append(repo_path)

        # --- Third check ('project')...
        if wanted_repo_key == 'project':
            repo_path = 'X:/tools/projects/{}'.format(project_name)
            repo_path += '/{0}_pipeline_{1}_{2}_repo'.format(
                proj_short_name,
                v_maj,
                v_min
            )

            if os.path.exists(repo_path):
                repo_paths.append(repo_path)

        # --- Always include the studio repo as the last repo path in the
        # --- list, and return the first entry from the list (the same if
        # --- there's only one entry in the list)...
        repo_paths.append(spr_path)

        return repo_paths

    def _tk_maya_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching a Maya session.
        """
        _setup = '_tk_maya_env_setup'
        self._headers(_setup)

        maya_script_paths = []
        maya_tool_paths = []
        self._module_paths = []
        plugin_paths = []

        for rp in self._repo_paths:
            maya_script_paths.append('{}/maya/scripts/mel'.format(rp))
            maya_script_paths.append('{}/maya/scripts/vtool'.format(rp))
            maya_script_paths.append('{}/maya/scripts/mel/anim'.format(rp))
            maya_script_paths.append('{}/maya/scripts/mel/light'.format(rp))
            maya_script_paths.append('{}/maya/scripts/mel/modeling'.format(rp))
            maya_script_paths.append('{}/maya/scripts/mel/rigging'.format(rp))

            maya_tool_path = '{}/maya/scripts'.format(rp)
            maya_tool_paths.append(maya_tool_path)

            module_path = '{}/maya/modules'.format(rp)
            self._module_paths.append(module_path)

            plugin_path = '{}/maya/plug-ins'.format(rp)
            plugin_paths.append(plugin_path)

        os.environ['MAYA_SCRIPT_PATH'] = os.pathsep.join(maya_script_paths)

        script_paths = []
        self._sg_a3_paths.reverse()
        script_paths.extend(self._sg_a3_paths)

        maya_tool_paths.reverse()
        script_paths.extend(maya_tool_paths)

        for sp in script_paths:
            sys.path.insert(0, sp)

            old_py_path = os.environ['PYTHONPATH']
            if sp in old_py_path.split(os.pathsep):
                m = 'Found {} in PYTHONPATH, no need to add it.'.format(sp)
                LOGGER.debug(m)
            else:
                old_py_path_bits = old_py_path.split(os.pathsep)
                old_py_path_bits.insert(0, sp)
                new_py_path = os.pathsep.join(old_py_path_bits)
                os.environ['PYTHONPATH'] = new_py_path
                LOGGER.debug('PYTHONPATH, added > {}'.format(sp))

        LOGGER.debug('old_py_path > {}'.format(old_py_path))
        LOGGER.debug('new_py_path > {}'.format(new_py_path))

        import python
        reload(python)

        if self._version in ['2018', '2020']:
            # --- Yeti version...
            self._yeti_vers = 'v3.1.10'
            if self._version == '2020':
                self._yeti_vers = 'v3.7.0'

            # --- Maya plug-in paths, general (server)...
            ppvs = []
            for pp in plugin_paths:
                pp_str = '{0}{1}{2}'.format(pp, os.sep, self._version)
                ppvs.append(pp_str)
            os.environ['MAYA_PLUG_IN_PATH'] = os.pathsep.join(ppvs)

            # --- Maya module paths, version (server)...
            # --- NOTE: additions should be placed in initial 'adds' list as
            #           follows, NOT 'module_list'
            main_module_list = []
            for mp in self._module_paths:
                mp = '{0}{1}{2}'.format(mp, os.sep, self._version)
                mp = mp.replace('\\', '/')
                LOGGER.debug('mp > {}'.format(mp))

                module_list = [mp]

                adds = [
                    'AtomsMaya',
                    'brSmoothWeights',
                    'houdiniEngine',
                    'iDeform',
                    'MayaBonusTools',
                    'SOUPopenVDB',
                    'yeti{0}{1}'.format(os.sep, self._yeti_vers),
                    'ziva'
                ]
                adds = ['{0}{1}{2}'.format(mp, os.sep, a) for a in adds]
                adds = [a.replace('\\', '/') for a in adds]

                module_list.extend(adds)
                main_module_list.extend(module_list)

            maya_module_path = os.pathsep.join(main_module_list)
            LOGGER.debug('maya_module_path > {}'.format(maya_module_path))
            os.environ['MAYA_MODULE_PATH'] = maya_module_path

            # --- NOTE TODO: THIS IS A LOCAL PATH
            # --- Arnold (experimental *NOT CALLED BY ANYTHING YET*
            # --- ~ DW 202-07-13)
            arnold_home = 'C:{0}solidangle{0}mtoadeploy{0}{1}'.format(
                os.sep,
                self._version
            )
            if self._version == '2020':
                arnold_home = '{0}{1}Autodesk{1}Arnold{1}maya{2}'.format(
                    self._wpf_root,
                    os.sep,
                    self._version
                )

            arnold_bin = '{0}{1}bin'.format(
                arnold_home,
                os.sep
            )
            LOGGER.debug('arnold_bin > {}'.format(arnold_bin))
            # TODO

            # --- VRay (legacy, we don't actually use it, but maybe for
            # --- retrieving old Assets?)...
            self._v_main_key = 'VRAY_FOR_MAYA{}_MAIN_x64'.format(self._version)
            self._v_plug_key = 'VRAY_FOR_MAYA{}_PLUGINS_x64'.format(
                self._version
            )
            self._tk_maya_env_setup_lcl_vray()

            # --- Yeti...
            self._tk_maya_env_setup_srv_yeti()

            # --- SOUP OpenVDB...
            self._tk_maya_env_setup_srv_soup_ovdb()

            # --- HoudiniEngine for Maya...
            self.tk_maya_env_setup_lcl_houdini_engine()

            # --- Redshift (legacy, we don't actually use it, but maybe for
            # --- retrieving old Assets?)...
            self._tk_maya_env_setup_lcl_redshift()

            # --- Arnold PATH cleanup at the end...
            self._tk_maya_env_setup_arnold_version_bin_fix()

            # --- AnimBot plugin
            self._tk_maya_env_setup_animbot()

        else:
            m = 'No Maya version specific environment variables required.'
            LOGGER.debug(m)

        # - Run cg factory path setup.
        self._tk_maya_env_setup_cgfactory()

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _tk_maya_env_setup_animbot(self):
        """Method to setup the config for animBot."""
        # https://help.animbot.ca/support/solutions/articles/61000292031-installing-enterprise-edition

        # TODO: Find a better place to put the config; don't hardcode this?
        os.environ['ANIMBOT_CONFIGJSONPATH'] = 'X:/tools/lic/config.json'

    def _tk_maya_env_setup_srv_yeti(self):
        """Method to set up all the wanted environment variables for Yeti with
        Arnold in a Maya session (in addition to earlier related module adds).
        """
        yeti_homes = []

        for mp in self._module_paths:
            yeti_home = '{0}{1}{2}{1}yeti{1}{3}'.format(
                mp,
                os.sep,
                self._version,
                self._yeti_vers
            )
            yeti_home = yeti_home.replace('\\', '/')
            LOGGER.debug('yeti_home > {}'.format(yeti_home))
            yeti_homes.append(yeti_home)

        # --- Yeti only respects one (1) path for YETI_HOME, so we check down
        # --- the list until we get one that exists...
        for y_item in yeti_homes:
            if os.path.exists(y_item):
                os.environ['YETI_HOME'] = y_item
                break

        yeti_home = y_item
        y_bin = '{0}{1}{2}bin'.format(os.pathsep, yeti_home, os.sep)
        y_bin = y_bin.replace('\\', '/')
        os.environ['PATH'] = '{0}{1}'.format(os.environ['PATH'], y_bin)

        y_icons = '{0}{1}{2}icons'.format(os.pathsep, yeti_home, os.sep)
        y_icons = y_icons.replace('\\', '/')
        os.environ['XBMLANGPATH'] = '{0}{1}'.format(
            os.environ['XBMLANGPATH'],
            y_icons
        )

        y_plugs = '{0}{1}{2}plug-ins'.format(os.pathsep, yeti_home, os.sep)
        y_plugs = y_plugs.replace('\\', '/')
        os.environ['MAYA_PLUG_IN_PATH'] = '{0}{1}'.format(
            os.environ['MAYA_PLUG_IN_PATH'],
            y_plugs
        )

        y_scrps = '{0}{1}{2}scripts'.format(os.pathsep, yeti_home, os.sep)
        y_scrps = y_scrps.replace('\\', '/')
        os.environ['MAYA_SCRIPT_PATH'] = '{0}{1}'.format(
            os.environ['MAYA_SCRIPT_PATH'],
            y_scrps
        )

        if 'VRAY_PLUGINS_x64' in os.environ.keys():
            os.environ['VRAY_PLUGINS_x64'] = '{0}{1}'.format(
                os.environ['VRAY_PLUGINS_x64'],
                y_bin
            )
        else:
            os.environ['VRAY_PLUGINS_x64'] = y_bin

        # --- Needed to get the module path in, as earlier just defines
        # --- the local Vray install path initially (DW 2020-07-09)
        if self._v_plug_key in os.environ.keys():
            os.environ[self._v_plug_key] = '{0}{1}'.format(
                os.environ[self._v_plug_key],
                y_bin
            )
        else:
            os.environ[self._v_plug_key] = y_bin
        # --- ^^^

        y_arn_keys = [
            'ARNOLD_PLUGIN_PATH',
            'MTOA_EXTENSIONS_PATH'
        ]
        for y_arn_key in y_arn_keys:
            if y_arn_key == y_arn_keys[0]:
                sub_dir = y_bin
            if y_arn_key == y_arn_keys[1]:
                sub_dir = y_plugs

            if y_arn_key in os.environ.keys():
                os.environ[y_arn_key] = '{0}{1}'.format(
                    os.environ[y_arn_key],
                    sub_dir
                )
            else:
                os.environ[y_arn_key] = sub_dir

    def _tk_maya_env_setup_srv_soup_ovdb(self):
        """Method to set up all the wanted environment variables for SOUP
        OpenVDB with Arnold in a Maya session (in addition to earlier related
        module adds).
        """
        soup_homes = []

        for mp in self._module_paths:
            soup_ovdb_home = '{0}{1}{2}{1}SOUPopenVDB'.format(
                mp,
                os.sep,
                self._version
            )

            soup_ovdb_home = soup_ovdb_home.replace('\\', '/')
            LOGGER.debug('soup_ovdb_home > {}'.format(soup_ovdb_home))
            soup_homes.append(soup_ovdb_home)

        for soup_ovdb_home in soup_homes:
            s_arn_keys = [
                'ARNOLD_PLUGIN_PATH',
                'MTOA_EXTENSIONS_PATH'
            ]
            for s_arn_key in s_arn_keys:
                sub_dir = ''
                if s_arn_key == s_arn_keys[0]:
                    sub_dir = '{0}arnold{0}shaders'.format(os.sep)
                if s_arn_key == s_arn_keys[1]:
                    sub_dir = '{0}arnold{0}extensions'.format(os.sep)

                if s_arn_key in os.environ.keys():
                    os.environ[s_arn_key] = '{0}{1}{2}{3}'.format(
                        os.environ[s_arn_key],
                        os.pathsep,
                        soup_ovdb_home,
                        sub_dir
                    )
                else:
                    os.environ[s_arn_key] = '{0}{1}{2}'.format(
                        soup_ovdb_home,
                        sub_dir
                    )

    def _tk_maya_env_setup_lcl_vray(self):
        """Method to set up all the wanted environment variables for VRay in a
        Maya session (no modules).
        """
        vray_home = '{0}{1}Autodesk{1}Maya{2}{1}vray'.format(
            self._wpf_root,
            os.sep,
            self._version
        )
        os.environ[self._v_main_key] = vray_home
        os.environ[self._v_plug_key] = '{0}{1}{2}'.format(
            vray_home,
            os.sep,
            'vrayplugins'
        )

        v_root = '{0}{1}Chaos Group{1}V-Ray{1}Maya {2} for x64'.format(
            self._wpf_root,
            os.sep,
            self._version
        )
        v_tools_key = 'VRAY_TOOLS_MAYA{}_x64'.format(self._version)
        os.environ[v_tools_key] = '{0}{1}bin'.format(
            v_root,
            os.sep
        )
        v_osl_key = 'VRAY_OSL_PATH_MAYA{}_x64'.format(self._version)
        os.environ[v_osl_key] = '{0}{1}opensl'.format(
            v_root,
            os.sep
        )

    def tk_maya_env_setup_lcl_houdini_engine(self):
        """Method to set up all the wanted local environment variables for
        HoudiniEngine for Maya in a Maya session (in addition to earlier
        related module adds).
        NOTE: again more weirdness with the Maya .mod file, which has this
            defined there but seems to be ignored, so we do it here...
            DW 2021-03-19
        """
        h_ver = '18.0.597'
        h_bin = 'C:/Program Files/Side Effects Software'
        h_bin += '/Houdini {}/bin'.format(h_ver)
        path_split = os.environ['PATH'].split(os.pathsep)
        if os.path.exists(h_bin) and h_bin not in path_split:
            os.environ['PATH'] = '{0}{1}{2}'.format(
                os.environ['PATH'],
                os.pathsep,
                h_bin
            )

    def _tk_maya_env_setup_lcl_redshift(self):
        """Method to set up all the wanted environment variables for Redshift
        in a Maya session (no modules).
        """
        r_core = 'C:/ProgramData/Redshift'
        r_plug_maya = '{}/Plugins/Maya'.format(r_core)
        r_common = '{}/Common'.format(r_plug_maya)

        os.environ['REDSHIFT_COREDATAPATH'] = r_core
        os.environ['REDSHIFT_PLUG_IN_PATH'] = '{0}/{1}/nt-x86-64'.format(
            r_plug_maya,
            self._version
        )
        os.environ['REDSHIFT_SCRIPT_PATH'] = '{}/scripts'.format(r_common)
        os.environ['REDSHIFT_XBMLANGPATH'] = '{}/icons'.format(r_common)
        os.environ['REDSHIFT_RENDER_DESC_PATH'] = '{}/rendererDesc'.format(
            r_common
        )
        _rctp = 'REDSHIFT_CUSTOM_TEMPLATE_PATH'
        os.environ[_rctp] = '{}/scripts/NETemplate'.format(r_common)
        _rmep = 'REDSHIFT_MAYAEXTENSIONSPATH'
        os.environ[_rmep] = '{0}/{1}/nt-x86-64/extensions'.format(
            r_plug_maya,
            self._version
        )
        os.environ['REDSHIFT_PROCEDURALSPATH'] = '{}/Procedural'.format(
            r_core
        )

    def _tk_maya_env_setup_cgfactory(self):
        """Add Maya environment relative to cg_factory submodule."""
        def append_to_env(env_var, *paths):
            # - Convert given paths to system default.
            paths = [os.path.normpath(p) for p in paths]

            # - If var is not already in env, make it.
            if env_var not in os.environ:
                os.environ[env_var] = os.pathsep.join(paths)
                return

            # - If env has envVar update paths to system default
            env_paths = [
                os.path.normpath(ep)
                for ep in os.environ[env_var].split(os.pathsep)
            ]
            # add each path as necessary
            for path in paths:
                # check if path already in values
                if path not in env_paths:
                    os.environ[env_var] = '{0}{1}{2}'.format(
                        os.environ[env_var],
                        os.pathsep,
                        path,
                    )
        # [end] appendToEnv

        # - Environment data.
        cgf_path = os.path.join(self._repo_path, 'maya/cg_factory/')

        env_dict = {
            'CG_FACTORY_PATH': [
                cgf_path,
            ],
            'PYTHONPATH': [
                cgf_path,
                '{}mayaConfigs/mayapy-extras/site-packages'.format(cgf_path),
                '{}mayaConfigs/scripts'.format(cgf_path),
                '{}assetPipeline'.format(cgf_path),
                '{}riggingPipeline'.format(cgf_path),
                '{}textureShadingPipeline'.format(cgf_path),
            ],
            'MAYA_SCRIPT_PATH': [
                cgf_path,
                '{}mayaConfigs/scripts'.format(cgf_path)
            ],
            'XBMLANGPATH': [
                '{}mayaConfigs/icons'.format(cgf_path),
                '{}mayaConfigs/projects/icons'.format(cgf_path)
            ],
            'MAYA_PLUG_IN_PATH': [
                # for python and root for mlls.
                '{}mayaConfigs/plugins'.format(cgf_path)
            ],
            'MAYA_MODULE_PATH': [
                '{}mayaConfigs/modules'.format(cgf_path)
            ],
        }

        # - Include plugin maya version if folder exists.
        plug_dir = os.path.join(
            env_dict['MAYA_PLUG_IN_PATH'][0],
            self._version
        )
        if os.path.isdir(plug_dir):
            env_dict['MAYA_PLUG_IN_PATH'].append(plug_dir)

        # - Add environments to system
        for env_k, env_v in env_dict.items():
            append_to_env(env_k, *env_v)

        # NOTE: do not try to get a python debugger (ie pdb trace).
        # does not work with shotgun launcher.

    def _tk_nuke_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching a Nuke session.
        """
        _setup = '_tk_nuke_env_setup'
        self._headers(_setup)

        # Update the sys.path
        script_paths = []
        script_paths.append(self._sg_a3_path)
        for script_path in script_paths:
            sys.path.insert(0, script_path)

        # Update the NUKE_PATH
        # - Previously, the I.T. department was configuring machines with the
        # - NUKE_PATH already set to 'x:\tools\nuke'
        # - This is now legacy and will be ignored when we launch nuke via the
        # - sgtk
        # - Also, log a warning if any NUKE_PATH already exists that is not a
        # - part of the expected "sgtk" launch mechanism
        nuke_plugin_path = []

        # Process the existing NUKE_PATH
        # - this is necessary to pickup the sgtk from the existing path
        if 'NUKE_PATH' in os.environ:
            nuke_paths = os.environ['NUKE_PATH'].split(os.pathsep)
            for nuke_path in nuke_paths:
                if 'sgtk' in nuke_path:
                    nuke_plugin_path.append(nuke_path)
                else:
                    m = 'Bad value in NUKE_PATH, ignoring: {}'.format(
                        nuke_path
                    )
                    LOGGER.warn(m)

        # Add main/dev pipeline repos to NUKE_PATH
        try:
            # old method
            sse_nuke_pipeline = '{}/nuke'.format(self._repo_path)
        except Exception:
            # new method:
            # Only take the first entry in the list, the rest are fallbacks and
            # are irrelevant for nuke.
            sse_nuke_pipeline = '{}/nuke'.format(self._repo_paths[0])

        sse_nuke_pipeline = sse_nuke_pipeline.replace('/', '\\')
        nuke_plugin_path.append(sse_nuke_pipeline)

        LOGGER.debug('Setting NUKE_PATH in os.environ...')
        os.environ['NUKE_PATH'] = os.pathsep.join(nuke_plugin_path)

        # Update SSE nuke tools paths
        # 1) SSE_NUKE_PIPELINE
        #    - location of TD controlled pipeline scripts/tools/templates/etc
        #    - This should match the location of the currently selected repo
        #    - (self._repo_paths[0])
        #
        # 2) SSE_NUKE_TOOLS
        #    - location of ARTIST controlled scripts/tools/templates/etc
        #    - For now, this is hard coded.
        #
        # TODO: support mac/linux paths?
        #
        LOGGER.debug('Setting SSE_NUKE_PIPELINE in os.environ...')
        os.environ['SSE_NUKE_PIPELINE'] = sse_nuke_pipeline

        LOGGER.debug('Setting SSE_NUKE_TOOLS in os.environ...')
        artist_tools = 'N:\\Resources\\Tools\\Nuke\\StudioTools'
        os.environ['SSE_NUKE_TOOLS'] = artist_tools

        # Prevent python from writing bytecode (avoids .pyc files)
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _tk_aftereffects_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching an AE session.
        """
        _setup = '_tk_aftereffects_env_setup'
        self._headers(_setup)

        script_paths = []
        script_paths.append(self._sg_a3_path)
        for script_path in script_paths:
            sys.path.insert(0, script_path)

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _tk_houdini_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching a Houdini session.
        """
        _setup = '_tk_houdini_env_setup'
        self._headers(_setup)

        # --- OCIO/ACES...
        os.environ['OCIO'] = OCIO_CONFIG
        os.environ['OCIO_ACTIVE_DISPLAYS'] = 'ACES'
        os.environ['OCIO_ACTIVE_VIEWS'] = 'Rec.709:sRGB:Raw:Log'
        os.environ['HOUDINI_OCIO_SRGB_FILE_COLORSPACE'] = \
            'Utility - Linear - sRGB'

        # --- houdini pipeline path
        houdini_path = os.environ["HOUDINI_PATH"]

        # adding studio repo_path
        os.environ['HOUDINI_PATH'] = '{0}{1}{2}'.format(
            houdini_path,
            os.pathsep,
            '{}/houdini/'.format(self._repo_path)
        )

        # custom libs and additional scripts
        hou_script_paths = []

        # --- NOTE: probably moving to houdini packages soon.

        hou_script_paths.append("@\\otls;N:\\Resources\\Tools\\Houdini\\shared\\otls")
        studio_hou_paths = os.pathsep.join(hou_script_paths)

        # houdini packages first move // adding custom packages reference dir
        # packages is new to houdini 17.5, allows customize different packages
        # the purpose here is just add a few common packages like qLIB and MOPS

        # HSITE is equivalent to houdini_path, required by HOUDINI_PACKAGE_DIR
        os.environ['HSITE'] = '{}/houdini/'.format(self._repo_path)
        os.environ['HOUDINI_PACKAGE_DIR'] = '{}/houdini/houdini18.5/packages'.format(self._repo_path)

        # adding custom scripts tools to houdini_otl_scanpath
        LOGGER.debug('Setting Custom Shared OTLS lib in HOUDINI_OTLSCAN_PATH...') 
        os.environ['SSE_SHARED_OTLS_PATH'] = "@;N:/Resources/Tools/Houdini/shared/otls"

        if 'HOUDINI_OTLSCAN_PATH' in os.environ:
             LOGGER.debug('Found existing HOUDINI_OTLSCAN_PATH in os.environ...')
             os.environ['HOUDINI_OTLSCAN_PATH'] = os.pathsep.join(
                 [
                     os.environ['HOUDINI_OTLSCAN_PATH'],
                     os.environ['SSE_SHARED_OTLS_PATH']
                 ]
             )
        else:
             m = 'No existing HOUDINI_OTL_SCANPATH in os.environ, creating...'
             LOGGER.debug(m)
             os.environ['HOUDINI_OTLSCAN_PATH'] = '{}'.format(studio_hou_paths)

        
        # sg api3 to houdini
        # test purpose - replacing sys.path insertion for pythonpath
        py_paths = []
        py_paths.append(self._sg_a3_path)

        for py_path in py_paths:
            os.environ['PYTHONPATH'] = '{0}{1}{2}'.format(
                os.environ['PYTHONPATH'],
                os.pathsep,
                py_path
            )
        m = 'New PYTHONPATH > {}'.format(os.environ['PYTHONPATH'])
        LOGGER.debug(m)

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _tk_natron_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching a Houdini session.
        """
        _setup = '_tk_natron_env_setup'
        self._headers(_setup)

        script_paths = []

        # --- NOTE: switch to the commented out line in the near future,
        # ---       'X:/tools/natron' is temporary...
        # studio_na_root='{}/natron'.format(self._repo_path).replace('/','\\')
        studio_na_root = 'X:/tools/natron'
        script_paths.append(studio_na_root)
        script_paths.append('{}/tools_sse'.format(studio_na_root))
        script_paths.append('{}/tools_sse/Plugins'.format(studio_na_root))
        script_paths.append(self._sg_a3_path)
        studio_na_paths = os.pathsep.join(script_paths)

        if 'NATRON_PLUGIN_PATH' in os.environ:
            LOGGER.debug('Found existing NATRON_PLUGIN_PATH in os.environ...')
            os.environ['NATRON_PLUGIN_PATH'] = os.pathsep.join(
                [
                    studio_na_paths,
                    os.environ['NATRON_PLUGIN_PATH']
                ]
            )
        else:
            m = 'No existing NATRON_PLUGIN_PATH in os.environ, creating...'
            LOGGER.debug(m)
            os.environ['NATRON_PLUGIN_PATH'] = '{}'.format(studio_na_paths)

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _tk_unreal_env_setup(self):
        """
        Method to set up all the wanted environment
        variables when launching an Unreal Engine session.
        """
        _setup = '_tk_unreal_env_setup'
        self._headers(_setup)

        project_name = os.environ['CURR_PROJECT']
        repo_path = self._return_repo_path(project_name)
        
        config_site_packages = os.path.join(
            repo_path, "unreal", "site-packages"
        )

        if not config_site_packages in os.environ.get("PYTHONPATH", ""):
            os.environ["PYTHONPATH"] += os.pathsep + config_site_packages

        # --- Tell the user what's up...
        self.env_paths_sanity_check()

    def _headers(self, user_title):
        """
        Print strings formatted as headers (with
        emphasis) to the console.
        @param str user_title: The title as a string to
                               fromat and print as a
                               header.
        """
        if user_title:
            LOGGER.debug(MY_SEP)
            LOGGER.debug(user_title)
            LOGGER.debug(MY_SEP)
        else:
            LOGGER.debug('Please provide a title string.')

    def env_paths_sanity_check(self):
        """
        Print the lists of source paths to the Shotgun
        Desktop Console.
        @param str engine_setup: represents the DCC setup
                                 we want to check against,
                                 which may have unique
                                 path variables.
        """
        env_var_str = []

        path_list = [
            'PATH',
            'SYS.PATH',
            'PYTHONPATH',
        ]

        # --- Per engine checks if required...
        if self._engine_name == 'tk-maya':
            _maya_paths = [
                'MAYA_MODULE_PATH',
                'MAYA_PLUG_IN_PATH',
                'MAYA_SCRIPT_PATH'
            ]

            path_list.extend(_maya_paths)

        if self._engine_name == 'tk-nuke':
            _nuke_paths = [
                'NUKE_PATH'
            ]
            path_list.extend(_nuke_paths)

        if self._engine_name == 'tk-aftereffects':
            pass

        if self._engine_name == 'tk-houdini':
            _houdini_paths = [
                'HOUDINI_PATH',
                'HOUDINI_OTLSCAN_PATH',
                'HSITE',
                'HOUDINI_PACKAGE_DIR'
            ]
            path_list.extend(_houdini_paths)

        if self._engine_name == 'tk-natron':
            _natron_paths = [
                'NATRON_PLUGIN_PATH',
            ]
            path_list.extend(_natron_paths)

        # --- Iterate over the paths...
        for path_item in path_list:
            env_var_str.append(MY_SEP)
            env_var_str.append(path_item)
            env_var_str.append(MY_SEP)

            if path_item == 'SYS.PATH':
                for item in sys.path:
                    env_var_str.append(item)
            else:
                for item in os.environ[path_item].split(';'):
                    env_var_str.append(item)

        env_var_str.append(MY_SEP)

        for env_var_item in env_var_str:
            LOGGER.debug(env_var_item)

    def _tk_maya_env_setup_arnold_version_bin_fix(self):
        """
        Get rid of the bad Arnold bin path from the PATH (mystery where it's
        coming from).
        """
        if self._version != '2018':
            bad_path = 'C:{0}solidangle{0}mtoadeploy{0}2018{0}bin'.format(
                os.sep
            )

            _os_env_paths = os.environ['PATH'].split(';')
            if bad_path in _os_env_paths:
                _os_env_paths.remove(bad_path)
                LOGGER.debug('Removed from PATH >> {}'.format(bad_path))
                _os_env_path_str = os.pathsep.join(_os_env_paths)
                os.environ['PATH'] = _os_env_path_str
# ---eof
