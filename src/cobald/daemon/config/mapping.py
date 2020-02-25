import logging
import logging.config
import sys
from typing import Any, Dict, TypeVar, Callable, Tuple, Generic, Set

from entrypoints import EntryPoint

_logger = logging.getLogger(__package__)


T = TypeVar("T")
#: type of a mapping element, matching JSON/YAML
M = TypeVar("M", str, int, float, bool, dict, list)


class ConfigurationError(Exception):
    def __init__(self, what: Any, where: str = None):
        self.where = where
        self.what = what
        super().__init__("invalid configuration element '%s': %s" % (where, what))


def configure_logging(logging_mapping: dict):
    _logger.info("Configuring logging")
    # > takes a default parameter, disable_existing_loggers, which defaults to True
    # > for reasons of backward compatibility. This may or may not be what you want
    # Note: this is *not* what we want, since we create several loggers in advance
    logging_mapping["disable_existing_loggers"] = logging_mapping.get(
        "disable_existing_loggers", False
    )
    logging.config.dictConfig(logging_mapping)


class Translator(object):
    """
    Translator from a mapping to an initialised object hierarchy
    """

    def translate_hierarchy(
        self, structure: M, *, where: str = "", **construct_kwargs
    ) -> M:
        try:
            if isinstance(structure, dict):
                structure = {
                    key: self.translate_hierarchy(value, where="%s.%s" % (where, key))
                    for key, value in structure.items()
                }
                if "__type__" in structure:
                    return self.construct(structure, **construct_kwargs)
                return structure
            elif isinstance(structure, list):
                # translate bottom up - need those lists to materialize
                # reversed and enumerate iterables
                return list(
                    reversed(
                        [
                            self.translate_hierarchy(
                                item, where="%s[%s]" % (where, index)
                            )
                            for index, item in reversed(list(enumerate(structure)))
                        ]
                    )
                )
            else:
                return structure
        except ConfigurationError as err:
            if err.where is None:
                raise ConfigurationError(what=err.what, where=where)
            raise
        except Exception as err:
            raise ConfigurationError(where=where, what=err)

    def construct(self, mapping: dict, **kwargs):
        """
        Construct an object from a mapping

        :param mapping: constructor definition, with ``__type__`` and keyword arguments
        :param kwargs: additional keyword arguments to pass to the constructor
        """
        assert "__type__" not in kwargs and "__args__" not in kwargs
        mapping = {**mapping, **kwargs}
        factory_fqdn = mapping.pop("__type__")
        factory = self.load_name(factory_fqdn)
        args = mapping.pop("__args__", [])
        return factory(*args, **mapping)

    @staticmethod
    def load_name(absolute_name: str):
        """Load an object based on an absolute, dotted name"""
        path = absolute_name.split(".")
        try:
            __import__(absolute_name)
        except ImportError:
            try:
                obj = sys.modules[path[0]]
            except KeyError:
                raise ImportError("No module named %r" % path[0])
            else:
                for component in path[1:]:
                    try:
                        obj = getattr(obj, component)
                    except AttributeError as err:
                        raise ConfigurationError(
                            what="no such object %r: %s" % (absolute_name, err)
                        )
                return obj
        else:  # ImportError is not raised if ``absolute_name`` points to a valid module
            return sys.modules[absolute_name]


class SectionPlugin(Generic[M]):
    """
    Plugin to digest a top-level configuration section

    :param section: Name of the section to digest
    :param digest: callable that receive the section
    :param required: whether the section must be present
    :param order: index of evaluating this plugin
    """
    __slots__ = "section", "digest", "required", "before", "after"

    __entry_point_flags__ = {"required"}

    def __init__(
        self,
        section: str,
        digest: Callable[[M], Any],
        required: bool = False,
        before: Set[str] = frozenset(),
        after: Set[str] = frozenset(),
    ):
        self.section = section
        self.digest = digest
        self.required = required
        self.before = before
        self.after = after

    @classmethod
    def load(cls, entry_point: EntryPoint) -> "SectionPlugin":
        """
        Load a plugin from a pre-parsed entry point

        Parses the following options:

        ``required``
            If present implies ``required=True``.

        ``before=other``
            This plugin must be processed before ``other``.

        ``after=other``
            This plugin must be processed after ``other``.
        """
        digest = entry_point.load()
        options = {"before": set(), "after": set(), "required": False}
        for option in (entry_point.extras or []):  # type: str
            # flags
            if option == "required":
                options["required"] = True
            # settings
            else:
                key, _, value = map(str.strip, option.partition('='))
                if key in ("before", "after"):
                    options[key].add(value)
                else:
                    raise ValueError(
                        f"unrecognized config section option {key}"
                        f" for SectionPlugin {entry_point.name}"
                    )
        return cls(
            section=entry_point.name,
            digest=digest,
            **options,
        )


def load_configuration(
    config_data: Dict[str, Any], plugins: Tuple[SectionPlugin] = ()
) -> Dict[SectionPlugin, Any]:
    """
    Load the configuration from a mapping

    :param config_data:
    :param plugins:
    :return:
    """
    try:
        logging_mapping = config_data.pop("logging")
    except KeyError:
        pass
    else:
        configure_logging(logging_mapping)
    # see if there is any unexpected config content
    unmatched = config_data.keys() - {plugin.section for plugin in plugins}
    if unmatched:
        raise ConfigurationError(
            where="root", what="unknown config sections %s" % ", ".join(unmatched)
        )
    content = {}
    for plugin in plugins:
        try:
            section_data = config_data[plugin.section]
        except KeyError:
            if plugin.required:
                raise ConfigurationError(
                    where="root", what="missing section %r" % plugin.section
                )
        else:
            # invoke the plugin and store possible output
            # to avoid it being garbage collected
            plugin_content = plugin.digest(section_data)
            if plugin_content is not None:
                content[plugin] = plugin_content
    return content
