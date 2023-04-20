import yaml
import logging
from typing import (List, Dict, Union, Any, Mapping, TypeVar, Generic, Tuple,
                    Iterable)
from copy import copy, deepcopy

from HFSSdrawpy import Modeler, Body
from HFSSdrawpy.utils import parse_entry, Vector


def deep_update(d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in u.items():
        if isinstance(v, Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class ImplementationError(Exception):
    "Raised there is an implementation error usign drawable."
    pass


_TL = TypeVar("_TL")


class DrawableElement:
    """Class used to draw with HFSSDrawpy object oriented.

    Attributes:
        _folder: The folder where to look for yaml files.
        _parent: Parent class of thype DrawableElement.
        _name: Name of element.
        _mode: Mode of drawing.
        _modeler: Modeler used for drawing.
        to_draw: Wheter to draw the element.
        Attributes sets in class file.

    Methods:
        children: Returns list of childrens.
        parent: Returns parent.
        name: Returns name.
        mode: Returns mode.
        create_yaml_file: Creates an empty yaml file.
        _draw: Classe to be redefined in element classes.
        draw: Draw the element.
    """

    _folder: str = None
    _parent: "DrawableElement" = None
    _name: str = None
    _mode: str = None
    _modeler: Modeler = None
    to_draw: bool = True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self._name}>"

    def __str__(self) -> str:
        string = ""
        for k in self.__dict__:
            attr = self.__dict__[k]
            if k != "_parent":
                if isinstance(attr, DrawableElement):
                    repr_subel = str(attr)
                    repr_subel = repr_subel.replace("\n", "\n  ")
                    string += f"{k}:\n  {repr_subel},\n"
                else:
                    if isinstance(attr, float):
                        string += f"{k}: {attr:.4e},\n"
                    else:
                        string += f"{k}: {attr},\n"
        return f"{string[:-2]}"

    def __init__(
        self,
        folder: str,
        params: Union[Dict[str, Any], str],
        modeler: Modeler,
        name: str,
        parent: "DrawableElement" = None
    ) -> None:
        """
        Parameters:
            folder: The folder containing yaml files.
            params: Dictionary containing the parameters of path to yaml file.
            modeler: Modeler used to_draw and set_variables.
            name: Name of the object.
            parent: Parent of the object.
        """

        if type(self).draw is not DrawableElement.draw:
            raise ImplementationError(f"""
                User should not override the draw method in class {type(self)}.
                He should implement _draw instead.
                """)

        logging.debug(f"Initializing {name}")

        self._folder = folder
        self._modeler = modeler
        self._mode = "None" if self._modeler is None else self._modeler.mode
        self._name = name
        self._parent = parent

        # If params is a yaml file, load it.
        if isinstance(params, str):
            dict_params = self._load_dict_from_file(params)
        else:
            dict_params = params

        # Load dictionary of children defined through a yaml.
        if self._parent is None:
            self._dict_params = self._load_files(dict_params)
        else:
            self._dict_params = dict_params

        # Run through the dictionary and set variables.
        attr_to_set, vars_to_set = self._parse_dict_params()

        # Set children attributes
        for k in attr_to_set:
            setattr(
                self, k, self.__annotations__[k](
                    self._folder,
                    self._dict_params[k],
                    self._modeler,
                    self._name + "_" + k,
                    parent=self
                )
            )

        # Set variations object
        for k in vars_to_set:
            setattr(self, k, self.__annotations__[k](variation={}))

        # Set variation elements
        for k, sub_dict in self._dict_params.items():
            splt = k.split("__")
            if splt[-1].isdigit():
                kv = splt[0]
                for el in splt[1:-1]:
                    kv += "__" + el
                indv = int(splt[-1])
                self._create_variation(sub_dict, kv, indv)

    def _load_files(self, dict_params: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in dict_params.items():
            if type(v) == str and v.endswith(".yaml"):
                dict_params[k] = self._load_dict_from_file(v)
        for k, v in dict_params.items():
            if type(v) == dict:
                dict_params[k] = self._load_files(v)
        return dict_params

    def _parse_dict_params(self) -> Tuple[List[str], List[str]]:
        """Function ro parse the dictionary parameters. Run through the
        attributes defined in class. Typing is used to determine how to set
        the attributes.

        Returns:
            attr_to_set: Attributes of type DrawableElement to set.
            vars_to_set: Variations to set.
        """

        attr_to_set = []
        vars_to_set = []
        for k, cls_name in self.__annotations__.items():
            if k in self._dict_params:
                if hasattr(cls_name, '__origin__'):
                    if issubclass(cls_name.__origin__, Variation):
                        vars_to_set.append(k)
                    elif issubclass(cls_name.__origin__, List):
                        self._set_list(
                            k, cls_name.__args__[0], self._dict_params[k])
                else:
                    if issubclass(cls_name, DrawableElement):
                        attr_to_set.append(k)
                    else:
                        self._set_element(k, cls_name, self._dict_params[k])
            elif not k.startswith("_"):
                self._search_in_parents(k)
        return attr_to_set, vars_to_set

    def _set_element(self, key: str, cls_name: type, value: Any) -> None:
        """Set an attribute of the class.

        Args:
            key (str): Key of the element in _dict_params.
            cls_name (type): Type of the element.
            value (Any): Value from _dict_params.
        """
        if (cls_name in [int, float, bool] or self._mode == "None" or 
            key.endswith("__n")):
            setattr(self, key, value)
        elif self._mode == "gds":
            setattr(self, key, parse_entry(value))
        else:
            setattr(
                self,
                key,
                self._modeler.set_variable(value, name=self.name + "_" + key))

    def _list_attr(
        self,
        cls_name: type,
        value_list: _TL,
        index: int = 0
    ) -> _TL:
        """Create parsed list of the element.

        Args:
            cls_name (type): Type of the attribute to set.
            value_list (_TL): List of values taken from _dict_params.
            index (int, optional): Index if multiple instances of the element.
                                   Defaults to 0.

        Returns:
            _TL: Iterable of parsed elements.
        """
        if hasattr(cls_name, '__origin__'):
            return [
                self._list_attr(cls_name.__args__[0], el, i)
                for i, el in enumerate(value_list)
            ]
        else:
            if cls_name in [int, float, bool] or self._mode == "None":
                return value_list
            elif self._mode == "gds":
                return Vector([parse_entry(v) for v in value_list])
            else:
                n_el = len(value_list)
                labels = ["x", "y", "z"] if n_el < 4 else range(n_el)
                return Vector([
                    self._modeler.set_variable(
                        v, name=f"{self.name}_{index}_{n}")
                    for n, v in zip(labels, value_list)
                ])

    def _set_list(self, key: str, cls_name: type, value_list: Any) -> None:
        setattr(self, key, self._list_attr(cls_name, value_list))

    def _search_in_parents(self, key: str) -> None:
        """Recursively run through the parents to find an attribute.

        Args:
            key (str): Key to search.

        Raises:
            KeyError: Raised if element is nowhere to be found in parents.
        """
        local_parent = copy(self._parent)
        while local_parent is not None:
            if key in local_parent.__dict__:
                setattr(self, key, local_parent.__dict__[key])
                return
            else:
                local_parent = local_parent.parent
        raise KeyError(
            f"Key {key} should be defined in .yaml file "
            + f"in {self.__class__.__name__} or "
            + "in it's parents.")

    def _load_dict_from_file(self, file_path: str) -> Dict[str, Any]:
        """Load Yaml file for an attribute parameters.

        Args:
            file_path (str): file_path that should end with '.yaml'.

        Raises:
            ValueError: If file_path do not end with '.yaml'.

        Returns:
            Dict[str, Any]: Loaded dictionary.
        """
        if not file_path.endswith(".yaml"):
            raise ValueError(
                f"Element {self._name} has dict params file that " +
                "does not ends with '.yaml'")
        with open(f"{self._folder}/{file_path}", 'r') as file:
            read = file.read()
            dict_par = yaml.safe_load(read)
        return dict_par

    def _complete_dict(self, sub_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Helper function to handle '.' definition of element in variations.

        Args:
            sub_dict (Dict[str, Any]): Dictionnary taken from variation.

        Returns:
            Dict[str, Any]: Dictionnary completed with full structure.
        """
        sub_dict = deepcopy(sub_dict)
        res, to_pop = {}, []
        for key, val in sub_dict.items():
            if "." not in key:
                res[key] = val
                to_pop.append(key)
        for el in to_pop:
            sub_dict.pop(el)
        for key, val in sub_dict.items():
            splt = key.split(".")
            local = res
            for k in splt[:-1]:
                if k not in local:
                    local[k] = {}
                local = local[k]
            local[splt[-1]] = val
        return res

    def _create_variation(self, sub_dict: Dict[str, Any], kv: str, indv: int):
        """Create copies of element to set in variation and update them with
        the variations dictionaries.

        Args:
            sub_dict (Dict[str, Any]): Variation dictionary
            kv (str): key of attribute to variate.
            indv (int): Index of variation.

        Raises:
            ValueError: When the core element is not defined.
        """
        var_dict = getattr(self, kv, None)
        if var_dict is None:
            raise ValueError(
                f"To have variation '{kv}__{indv}', the attribute" +
                f" '{kv}' should be defined in class.")
        variation = deepcopy(self._dict_params[kv])
        if sub_dict is not None:
            sub_dict = self._complete_dict(sub_dict)
            variation = deep_update(variation, sub_dict)
        var_dict[indv] = self.__annotations__[kv].__args__[0](
                self._folder,
                variation,
                self._modeler,
                self._name + f"_{kv}_{indv}",
                parent=self
            )

    @property
    def children(self) -> List["DrawableElement"]:
        """Returns the list of children of this DrawableElement.

        Returns:
            List["DrawableElement"]: Childrens.
        """
        children = []
        for k in self.__dict__:
            if (
                isinstance(self.__dict__[k], DrawableElement) and
                not k.startswith("_")
            ):
                children.append(k)
        return children

    @property
    def parent(self) -> "DrawableElement":
        return self._parent

    @property
    def name(self) -> str:
        return self._name

    @property
    def mode(self) -> str:
        return self._mode

    def _create_dictionary(self) -> Dict[str, str]:
        """Helper function to wwrite the empty yaml file.

        Returns:
            Dict[str, str]: Dictionary of class structure.
        """
        dico_params = {}
        for key, attr in self.__dict__.items():
            if not key.startswith("_"):
                if isinstance(attr, DrawableElement):
                    dico_params[key] = attr._create_dictionary()
                else:
                    dico_params[key] = ""
        return dico_params

    def create_yaml_file(self, filename: str, folder: str = None) -> None:
        """Helper function to create a yaml file with the class' structure.
        One should keep in mind that elements defined in parents will be
        redifined in children with this class.

        Args:
            filename (str): file to be created.
            folder (str, optional): Folder in wich file should be created.
        """
        if folder is None:
            folder = self._folder
        with open(self._folder+"/"+filename, 'w') as file:
            yaml.safe_dump(self._create_dictionary(), file)

    def _check_existing_path(self, path: str) -> bool:
        local_attr = self
        splt = path.split(".")
        for k in splt:
            if isinstance(local_attr, Variation):
                local_attr = local_attr[list(local_attr.keys())[0]]
            local_attr = getattr(local_attr, k, None)
            if local_attr is None:
                attrs = [el for el in dir(local_attr)
                         if not el.startswith("_")]
                raise ValueError(
                    f"Path of variation {path} does not exist at {k}." +
                    f"The possiblities are {attrs}")
        return True

    def _create_dictionary_variation(
        self,
        sub_key: str,
        sub_len: int,
        sub_variation: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = {}
        for ind in range(sub_len):
            result[f"{sub_key}__{ind}"] = {}
            for k, var_lst in sub_variation.items():
                splt = k.split(".")
                if splt[0] != sub_key:
                    raise ImplementationError(
                        f"Subvariation ({splt}) is not for the right key " +
                        "({sub_key})")
                local = result[f"{sub_key}__{ind}"]
                for k in splt[1:-1]:
                    if k not in local:
                        local[k] = {}
                    local = local[k]
                if splt[-1] in local:
                    raise ValueError("Same variable is sweeped twice.")
                local[splt[-1]] = var_lst[ind]
        return result

    def create_variation_yaml_file(
        self,
        variation: Dict[str, Iterable],
        filename: str,
        folder: str = None
    ) -> None:
        """Helper function to write a variation yaml file based on current
        defining yaml files.

        Variation is a dictionary:
            keys are path in the parameters dictionary. For example
            'transmon.junction.lj'
            values are Iterable of same lengths."""

        dict_vars_len = {}
        dict_vars_div = {}
        for k, v in variation.items():
            self._check_existing_path(k)
            k_0 = k.split(".")[0]
            if k_0 in dict_vars_len:
                if len(v) != dict_vars_len[k_0]:
                    raise ValueError(
                        f"All variation of {k_0} should be the same lengths.")
                dict_vars_div[k_0][k] = v
            else:
                dict_vars_len[k_0] = len(v)
                dict_vars_div[k_0] = {k: v}

        yaml_dict = deepcopy(self._dict_params)
        to_pop = []
        for k in yaml_dict.keys():
            splt = k.split("__")
            if splt[-1].isdigit():
                to_pop.append(k)
        for k in to_pop:
            yaml_dict.pop(k)

        for key, subvar in dict_vars_div.items():
            sub_dict = self._create_dictionary_variation(
                key, dict_vars_len[key], subvar)
            yaml_dict.update(sub_dict)

        if folder is None:
            folder = self._folder
        with open(self._folder+"/"+filename, 'w') as file:
            yaml.safe_dump(yaml_dict, file)

    def _draw(self, body: Body, **kwargs) -> None:
        """Core function to draw an element. This is the one that should be
        overwritten in the classes deriving from DrawableElement.
        """
        for k in self.children:
            attribute = getattr(self, k)
            attribute.draw(body, **kwargs)
        if len(self.children) == 0:
            raise NotImplementedError(
                f"_draw() of {self.__class__.__name__} is not implemented")

    def draw(self, body: Body, **kwargs) -> None:
        """Call _draw if if object is 'to_draw'.
        """
        if self.to_draw:
            logging.debug(f"Drawing {self.name}")
            self._draw(body, **kwargs)


_Tvar = TypeVar("_Tvar", bound=DrawableElement)


class Variation(Generic[_Tvar]):
    """Class to handle variation of an element."""

    variation: Dict[int, _Tvar]
    to_draw: bool = True

    _len: int

    def __init__(
        self,
        variation: Dict[int, _Tvar],
    ):
        self._variations = variation
        self._keys = list(self._variations.keys())
        self._len = len(self._keys)

    def __setitem__(self, key: int, value: _Tvar):
        is_in = key in self._variations
        self._variations[key] = value
        if not is_in:
            self._keys = list(self._variations.keys())
            self._len += 1

    def __getitem__(self, key: int) -> _Tvar:
        return self._variations[key]

    def __iter__(self) -> "Variation":
        self._n_iter = 0
        return self

    def __next__(self) -> _Tvar:
        if self._n_iter < self._len:
            result = self._variations[self._keys[self._n_iter]]
            self._n_iter += 1
            return result
        else:
            raise StopIteration

    def keys(self) -> Iterable:
        return self._variations.keys()

    def draw(self, **kwargs) -> None:
        if self.to_draw:
            for el in self._variations.values():
                el.draw(**kwargs)
