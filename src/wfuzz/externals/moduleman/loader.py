import inspect
import logging
import importlib.util
import os

class IModuleLoader:
    def __init__(self, **params):
        self.set_params(**params)

    def set_params(self, **params):
        raise NotImplementedError

    def load(self, registrant):
        raise NotImplementedError


class FileLoader(IModuleLoader):
    def __init__(self, **params):
        super().__init__(**params)
        self.__logger = logging.getLogger("libraries.FileLoader")

    def set_params(self, **params):
        if "base_path" not in params or "filename" not in params:
            return
        
        self.filename = params["filename"]
        self.base_path = params["base_path"]
        if self.base_path.endswith("/"):
            self.base_path = self.base_path[:-1]

    def load(self, registrant):
        self.module_registrant = registrant
        self._load_py_from_file(os.path.join(self.base_path, self.filename))

    def _build_id(self, filename, objname):
        filepath, _ = os.path.split(filename)
        relative_path = os.path.relpath(filepath, self.base_path)
        identifier = os.path.join(relative_path, objname)
        return identifier.lstrip('./')

    def _load_py_from_file(self, filename):
        """
        Opens "filename", inspects it, and calls the registrant.
        """
        self.__logger.debug("__load_py_from_file. START, file=%s", filename)

        if not os.path.isfile(filename):
            self.__logger.critical("File not found: %s", filename)
            return

        module_name = os.path.splitext(os.path.basename(filename))[0]

        spec = None
        module = None

        try:
            spec = importlib.util.spec_from_file_location(module_name, filename)
            if spec is None:
                raise ImportError(f"Cannot find module spec for file {filename}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except (ImportError, SyntaxError) as e:
            self.__logger.critical("__load_py_from_file. Filename: %s Exception, msg=%s", filename, str(e))
        except Exception as e:
            self.__logger.critical("__load_py_from_file. Filename: %s Exception, msg=%s", filename, str(e))
        finally:
            if spec and spec.loader and hasattr(spec.loader, 'get_data'):
                spec.loader.get_data(filename)

        if module is None:
            return

        for objname in dir(module):
            obj = getattr(module, objname)
            self.__logger.debug("__load_py_from_file. inspecting=%s", objname)
            if inspect.isclass(obj):
                if "__PLUGIN_MODULEMAN_MARK" in dir(obj):
                    if self.module_registrant:
                        self.module_registrant.register(
                            self._build_id(filename, objname), obj
                        )

        self.__logger.debug("__load_py_from_file. END, loaded file=%s", filename)


class DirLoader(FileLoader):
    def __init__(self, **params):
        super().__init__(**params)
        self.__logger = logging.getLogger("libraries.DirLoader")

    def set_params(self, **params):
        if "base_dir" not in params or "base_path" not in params:
            return

        self.base_dir = params["base_dir"]
        self.base_path = params["base_path"]
        if self.base_path.endswith("/"):
            self.base_path = self.base_path[:-1]

    def load(self, registrant):
        self.module_registrant = registrant
        base_directory = os.path.join(self.base_path, self.base_dir)
        self.__logger.debug("Loading directory: %s", base_directory)
        self.structure = self.__load_all(base_directory)

    def _build_id(self, filename, objname):
        filepath, _ = os.path.split(filename)
        relative_path = os.path.relpath(filepath, os.path.join(self.base_path, self.base_dir))
        identifier = os.path.join(relative_path, objname)
        return identifier.lstrip('./')

    def __load_all(self, dir_name):
        """
        Loads all plugins and creates a loaded list of scripts from directory plugins.
        """
        walked = []
        if os.path.isdir(dir_name):
            dir_list = self.__walk_dir_tree(dir_name)
            walked.append((dir_name, dir_list))
            if self.module_registrant:
                self.module_registrant.end_loading()
        return walked

    def __walk_dir_tree(self, dirname):
        dir_list = []
        self.__logger.debug("__walk_dir_tree. START dir=%s", dirname)

        if not os.path.isdir(dirname):
            self.__logger.error("Directory does not exist: %s", dirname)
            return dir_list

        for f in os.listdir(dirname):
            current = os.path.join(dirname, f)
            if os.path.isfile(current) and f.endswith(".py"):
                self.__logger.debug("Found Python file: %s", current)
                if self.module_registrant:
                    self._load_py_from_file(current)
                dir_list.append(current)
            elif os.path.isdir(current):
                self.__logger.debug("Found directory: %s", current)
                ret = self.__walk_dir_tree(current)
                if ret:
                    dir_list.append((f, ret))

        return dir_list
