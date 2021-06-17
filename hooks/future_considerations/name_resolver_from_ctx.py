from sgtk import Hook
import os


class ProceduralNameFromContext(Hook):
    """
    """

    def execute(self, setting, bundle_obj, extra_params, **kwargs):
        """
        Get a name from the current context

        :param setting: The name of the setting for which we are evaluating
                        In our example above, it would be template_snapshot.

        :param bundle_obj: The app, engine or framework object that the setting
                           is associated with.

        :param extra_params: List of options passed from the setting. If the settings
                             string is "hook:hook_name:foo:bar", extra_params would
                             be ['foo', 'bar']

        returns: needs to return the name of the file, as a string
        """

        resolve_mode = extra_params[0]
        # the mode is basically the parameter passed from the config value - in this case task_name

        if resolve_mode == "task_name":
            ctx_task = bundle_obj.context.task
            return ctx_task["name"] if ctx_task else "scene"
        elif resolve_mode == "entity_name":
            ctx_entity = bundle_obj.context.entity
            return ctx_entity["name"] if ctx_entity else "scene"
        else:
            return "scene"