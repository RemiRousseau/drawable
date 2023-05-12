from typing import (Final, List, Dict, Optional, Protocol, Type, Union, Any,
                    TypeVar, Tuple, Generic, Iterable, final)
import os
from copy import copy, deepcopy
import yaml
import logging

try:
    # from HFSSdrawpy import Modeler, Body
    from HFSSdrawpy.utils import parse_entry, Vector
except ModuleNotFoundError:
    Vector = list

    def parse_entry(*args):
        return args


class Modeler(Protocol):
    """Protocol for Modeler from HFSSdrawpy."""

    mode: str

    def set_variable(self, value, name):
        ...


class Body(Protocol):
    """Protocol for Body from HFSSdrawpy."""


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s:%(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def deep_update(
        base_dict: Dict[str, Any],
        update: Dict[str, Any]
) -> Dict[str, Any]:
    """Update nested dictionaries."""
    for key, value in update.items():
        if hasattr(value, 'get'):
            base_dict[key] = deep_update(
                base_dict.get(key, {}), value)
        else:
            base_dict[key] = value
    return base_dict


_TL = TypeVar("_TL")


class ImplementationError(Exception):
    """Raise on an implementation error using drawable."""


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

    __annotations__: dict[str, Union[Any, Type["DrawableElement"]]]
    _folder: str
    _parent: Optional["DrawableElement"] = None
    _name: str
    _mode: str
    _modeler: Optional[Modeler] = None
    to_draw: bool = True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self._name}>"

    def __str__(self) -> str:
        string = ""
        for key, attr in self.__dict__.items():
            # attr = self.__dict__[k]
            if key != "_parent":
                if isinstance(attr, DrawableElement):
                    repr_subel = str(attr).replace("\n", "\n  ")
                    string += f"{key}:\n  {repr_subel},\n"
                elif isinstance(attr, float):
                    string += f"{key}: {attr:.4e},\n"
                else:
                    string += f"{key}: {attr},\n"
        return f"{string[:-2]}"

    def __init__(
        self,
        folder: str,
        params: Union[Dict[str, Any], str],
        name: str,
        modeler: Optional[Modeler] = None,
        parent: Optional["DrawableElement"] = None
    ) -> None:
        """Init.

        Parameters:
            folder: The folder containing yaml files.
            params: Dictionary containing the parameters of path to yaml file.
            modeler: Modeler used to_draw and set_variables.
            name: Name of the object.
            parent: Parent of the object.
        """
        if type(self).draw is not DrawableElement.draw:
            raise ImplementationError(
                f"User should not override the draw method in class {type(self)}."
                "He should implement _draw instead.")

        logger.debug("Initializing %s", name)

        self._folder = folder
        self._modeler: Final = modeler
        self._mode: Final = "None" if self._modeler is None else self._modeler.mode
        self._name = name
        self._parent: Final = parent

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
        attrs_to_set, vars_to_set = self._parse_dict_params()

        # Set children attributes
        for attr in attrs_to_set:
            setattr(
                self, attr, self.__annotations__[attr](
                    self._folder,
                    self._dict_params[attr],
                    self._name + "_" + attr,
                    self._modeler,
                    parent=self
                )
            )

        # Set variat ions object
        for attr, cls in vars_to_set:
            original = cls(
                self._folder,
                self._dict_params[attr],
                self._name + "_" + attr,
                self._modeler,
                parent=self
            )
            setattr(self, attr, self.__annotations__[attr](  # type: ignore
                variation=[],  # type: ignore
                original=original,  # type: ignore
            ))

        # Set variation elements
        for attr, sub_dict in self._dict_params.items():
            splt = attr.split("__")
            if splt[-1].isdigit():
                var_key = splt[0]
                for elm in splt[1:-1]:
                    var_key += "__" + elm
                var_index = int(splt[-1])
                self._create_variation(sub_dict, var_key, var_index)

    def _load_files(self, dict_params: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in dict_params.items():
            if isinstance(v, str) and v.endswith(".yaml"):
                dict_params[k] = self._load_dict_from_file(v)
        for k, v in dict_params.items():
            if isinstance(v, dict):
                dict_params[k] = self._load_files(v)
        return dict_params

    def _parse_dict_params(self) -> Tuple[List[str],
                                          List[Tuple[str, Type['DrawableElement']]]]:
        """Assign values from self._dict_param to attr.

        Run through the attributes defined in class.
        Typing is used to determine how to set the attributes.
        Returns:
            attr_to_set: Attributes of type DrawableElement to set.
            vars_to_set: Variations to set.
        """
        attr_to_set = []
        variations_to_set = []
        for key, cls_name in self.__annotations__.items():
            if key in self._dict_params:
                if hasattr(cls_name, '__origin__'):
                    if issubclass(cls_name.__origin__, Variation):  # type: ignore
                        variations_to_set.append([key, cls_name.__args__[0]])  # type: ignore
                    elif issubclass(cls_name.__origin__, List):  # type: ignore
                        self._set_list(
                            key, cls_name.__args__[0], self._dict_params[key])  # type: ignore
                    else:
                        raise ValueError(
                            f"Unknown type {cls_name}. Should be either Variation or List.")
                elif issubclass(cls_name, DrawableElement):
                    attr_to_set.append(key)
                else:
                    self._set_element(key, cls_name, self._dict_params[key])
            elif not key.startswith("_"):
                self._search_in_parents(key)

        return attr_to_set, variations_to_set

    def _set_element(self, key: str, cls_name: type, value: Any) -> None:
        """Set an attribute of the class to a value.

        Args:
            key (str): Key of the element in _dict_params.
            cls_name (type): Type of the element.
            value (Any): Value from _dict_params.
        """
        if (cls_name in [int, float, bool] or
                self._modeler is None or
                key.endswith("__n")):
            setattr(self, key, value)
        elif self._mode == "gds":
            setattr(self, key, parse_entry(value))
        else:
            setattr(
                self,
                key,
                self._modeler.set_variable(
                    value, name=self.name + "_" + key))

    def _list_attr(
        self,
        cls_name: type,
        value_list,
        key: Union[str, int],
        index: int = 0
    ):
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
                self._list_attr(cls_name.__args__[0], elm, i)  # type: ignore
                for i, elm in enumerate(value_list)
            ]

        if cls_name in [int, float, bool] or self._mode == "None":
            return value_list
        if self._mode == "gds":
            return Vector([parse_entry(v) for v in value_list])

        n_el = len(value_list)
        labels = ["x", "y", "z"] if n_el < 4 else range(n_el)
        return Vector([
            self._modeler.set_variable(  # type: ignore
                v, name=f"{self.name}_{key}_{index}_{n}")
            for n, v in zip(labels, value_list)
        ])

    def _set_list(self,
                  key: str,
                  cls_name: type,
                  value_list: Any) -> None:
        setattr(self, key, self._list_attr(cls_name, value_list, key))

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
            f"in {self.__class__.__name__} or "
            "in it's parents.")

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
                f"Element {self._name} has dict params file that "
                f"does not ends with '.yaml': {file_path}")

        with open(f"{self._folder}/{file_path}", 'r', encoding="utf-8") as file:
            return yaml.safe_load(file.read())

    @staticmethod
    def _complete_dict(sub_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Reformat flatten dict with '.' in keys into a tree structure.

        Args:
            sub_dict (Dict[str, Any]): Dictionnary taken from variation.

        Examples:
            {'a':1, 'b.c': 3} -> {'a': 2, 'b': {'c': 3} }

        Returns:
            Dict[str, Any]: Dictionnary completed with full structure.
        """
        sub_dict = deepcopy(sub_dict)
        full_dict = {}

        for key, val in list(sub_dict.items()):
            if "." not in key:
                full_dict[key] = val
                continue
            splt = key.split(".")
            local = full_dict
            for k in splt[:-1]:
                local = local.setdefault(k, {})
            local[splt[-1]] = val
        return full_dict

    def _create_variation(self, sub_dict: Dict[str, Any], kv: str, indv: int):
        """Create copies of the element variate the attribute given by kv.

        Args:
            sub_dict (Dict[str, Any]): Variation dictionary
            kv (str): key of attribute to variate.
            indv (int): Index of variation.

        Raises:
            ValueError: When the core element is not defined.
        """
        var_lst = getattr(self, kv, None)
        if var_lst is None:
            raise ValueError(
                f"To have variation '{kv}__{indv}', the attribute "
                f"'{kv}' should be defined inside the class.")
        variation = deepcopy(self._dict_params[kv])
        if sub_dict is not None:
            sub_dict = self._complete_dict(sub_dict)
            variation = deep_update(variation, sub_dict)
        var_lst.append(self.__annotations__[kv].__args__[0](  # type: ignore
            self._folder,
            variation,
            self._modeler,
            self._name + f"_{kv}_{indv}",
            parent=self
        ))

    @property
    def children(self) -> List[str]:
        """Return the list of children of this DrawableElement.

        Returns:
            List["DrawableElement"]: Children.
        """
        children: List[str] = []
        for var_name, var_type in self.__dict__.items():
            if (
                isinstance(var_type, DrawableElement) and
                not var_name.startswith("_")
            ):
                children.append(var_name)
        return children

    @property
    def parent(self) -> Optional["DrawableElement"]:
        return self._parent

    @property
    def name(self) -> str:
        return self._name

    @property
    def reduced_name(self) -> str:
        splt = self._name.split("_")
        n_max = 30
        name = splt.pop()
        name_len = len(name)
        for elm in splt[::-1]:
            elm_len = len(elm)
            if elm_len + name_len >= n_max:
                return name

            name = elm + "_" + name
            name_len += elm_len + 1
        return name

    @property
    def mode(self) -> str:
        return self._mode

    def _create_dictionary(self) -> Dict[str, str]:
        """Create empty dictionary with parameters from __dict__.

        Helper function to write the empty yaml file.
        Returns:
            Dict[str, str]: Dictionary of class structure.
        """
        params = {}
        for key, attr in self.__dict__.items():
            if key.startswith("_"):
                continue
            params[key] = attr._create_dictionary() \
                if isinstance(attr, DrawableElement) else ""  # pylint: disable=W0212

        return params

    def create_yaml_file(self,
                         filename: str,
                         folder: Optional[str] = None) -> None:
        """Create dictionary with empty parameters and save it to yaml file.

        Helper function to create a yaml file with the class' structure.
        One should keep in mind that elements defined in parents will be
        redefined in children with this class.
        Args:
            filename (str): file to be created.
            folder (str, optional): Folder in wich file should be created.
        """
        if folder is None:
            folder = self._folder
        with open(os.path.join(self._folder, filename), 'w', encoding="utf-8") as file:
            yaml.safe_dump(self._create_dictionary(), file)

    def _check_existing_path(self, path: str) -> bool:
        local_attr = self
        splt = path.split(".")
        for k in splt:
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
                        f"Subvariation ({splt}) is not for the right key "
                        f"({sub_key})")
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
        folder: Optional[str] = None
    ) -> None:
        """Create a yaml files for every variation.

        Helper function to write a variation yaml file based on current
        defining yaml files.

        Variation is a dictionary:
            keys are path in the parameters dictionary. For example
            'transmon.junction.lj'
            values are Iterable of same lengths.
        """
        dict_vars_len = {}
        dict_vars_div = {}
        for key, value in variation.items():
            self._check_existing_path(key)
            k_0 = key.split(".")[0]
            if k_0 in dict_vars_len:
                if len(value) != dict_vars_len[k_0]:  # type: ignore
                    raise ValueError(
                        f"All variation of {k_0} should be the same lengths.")
                dict_vars_div[k_0][key] = value
            else:
                dict_vars_len[k_0] = len(value)  # type: ignore
                dict_vars_div[k_0] = {key: value}

        yaml_dict = deepcopy(self._dict_params)

        to_pop = []
        for key in yaml_dict.keys():
            splt = key.split("__")
            if splt[-1].isdigit():
                to_pop.append(key)

        for key in to_pop:
            yaml_dict.pop(key)

        for key, subvar in dict_vars_div.items():
            sub_dict = self._create_dictionary_variation(
                key, dict_vars_len[key], subvar)
            yaml_dict.update(sub_dict)

        if folder is None:
            folder = self._folder

        with open(os.path.join(self._folder, filename), 'w', encoding="utf-8") as file:
            yaml.safe_dump(yaml_dict, file)

    def _draw(self, body: Body, **kwargs) -> None:
        """Can be overwritten. Otherwise call function draw on every child.

        Core function to draw an element. This is the one that should be
        overwritten in the classes deriving from DrawableElement.
        """
        for child in self.children:
            attribute: DrawableElement = getattr(self, child)
            attribute.draw(body, **kwargs)

        if len(self.children) == 0:
            raise NotImplementedError(
                f"_draw() of {self.__class__.__name__} is not implemented")

    @final
    def draw(self, body: Body, **kwargs) -> None:
        """Call _draw if if object is 'to_draw'."""
        if self.to_draw:
            logger.debug("Drawing %s", self.name)
            self._draw(body, **kwargs)


_Tvar = TypeVar("_Tvar", bound=DrawableElement)


class Variation(Generic[_Tvar]):
    """Class to handle variation of an element."""

    variations: List[_Tvar]
    to_draw: bool = True

    _len: int
    _n_iter: int = 0

    def __init__(
        self,
        variation: List[_Tvar],
        original: _Tvar,
    ):
        self.variations = variation
        self._len = len(self.variations)
        for attr, value in original.__dict__.items():
            if not attr.startswith('_'):
                setattr(self, attr, value)

    def __iter__(self) -> "Variation":
        self._n_iter = 0
        return self

    def __getitem__(self, item):
        return self.variations[item]

    def __next__(self) -> _Tvar:
        if self._n_iter < self._len:
            result = self.variations[self._n_iter]
            self._n_iter += 1
            return result
        raise StopIteration

    def __len__(self):
        return self._len

    def append(self, elm: _Tvar) -> None:
        self._len += 1
        self.variations.append(elm)

    @final
    def draw(self, body: Body, **kwargs) -> None:
        if self.to_draw:
            for elm in self.variations:
                elm.draw(body=body, **kwargs)
