import yaml
import logging
from typing import List, Dict, Union, Any, Mapping, TypeVar, Generic, Tuple
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
    _folder: str
    _parent: "DrawableElement" = None
    _name: str
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

        if isinstance(params, str):
            self._dict_params = self._load_dict_from_file(params)
        else:
            self._dict_params = params

        attr_to_set, vars_to_set = self._parse_dict_params()

        for k in attr_to_set + vars_to_set:
            if isinstance(self._dict_params[k], str):
                self._dict_params[k] = self._load_dict_from_file(
                    self._dict_params[k])

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

        for k in vars_to_set:
            setattr(self, k, self.__annotations__[k](variation={}))

        for k, sub_dict in self._dict_params.items():
            splt = k.split("__")
            if len(splt) > 2:
                raise ValueError(
                    f"Variable {k} in config should " +
                    "contain maximum one '__'."
                )
            if len(splt) == 2 and splt[1].isdigit():
                self._create_variation(sub_dict, *splt)

    def _parse_dict_params(self) -> Tuple[List[str], List[str]]:
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
        if cls_name in [int, float, bool] or self._mode == "None":
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
        if not file_path.endswith(".yaml"):
            raise ValueError(
                f"Element {self._name} has dict params file that " +
                "does not ends with '.yaml'")
        with open(f"{self._folder}/{file_path}", 'r') as file:
            read = file.read()
            dict_par = yaml.safe_load(read)
        return dict_par

    def _create_variation(self, sub_dict: Dict[str, Any], kv: str, indv: int):
        var_dict = getattr(self, kv, None)
        if var_dict is None:
            raise ValueError(
                f"To have variation '{kv}__{indv}', the attribute" +
                f" '{kv}' should be defined in class.")
        if sub_dict is not None:
            variation = deep_update(
                deepcopy(self._dict_params[kv]), sub_dict)
        var_dict[indv] = self.__annotations__[kv].__args__[0](
                self._folder,
                variation,
                self._modeler,
                self._name + f"_{kv}_{indv}",
                parent=self
            )

    @property
    def children(self) -> List["DrawableElement"]:
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

    def _draw(self, body: Body, **kwargs) -> None:
        for k in self.children:
            attribute = getattr(self, k)
            attribute.draw(body, **kwargs)
        if len(self.children) == 0:
            raise NotImplementedError(
                f"_draw() of {self.__class__.__name__} is not implemented")

    def draw(self, body: Body, **kwargs) -> None:
        if self.to_draw:
            logging.debug(f"Drawing {self.name}")
            self._draw(body, **kwargs)


_Tvar = TypeVar("_Tvar", bound=DrawableElement)


class Variation(Generic[_Tvar]):
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

    def draw(self, **kwargs) -> None:
        if self.to_draw:
            for el in self._variations.values():
                el.draw(**kwargs)
