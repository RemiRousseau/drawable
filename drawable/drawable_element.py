import yaml
from typing import List, Dict, Union, Any, Generic, TypeVar
from copy import copy, deepcopy
import collections.abc

from HFSSdrawpy import Modeler, Body
from HFSSdrawpy.utils import parse_entry


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class ImplementationError(Exception):
    "Raised there is an implementation error usign drawable."
    pass


class DrawableElement:
    _parent = None
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
        params: Union[Dict[str, Any], str],
        modeler: Modeler,
        name: str,
        parent=None
    ) -> None:

        if isinstance(params, str):
            self._dict_params = self._load_dict_from_file(params)
        else:
            self._dict_params = params

        self._modeler = modeler
        self._mode = "None" if self._modeler is None else self._modeler.mode
        self._name = name
        self._parent = parent

        if type(self).draw is not DrawableElement.draw:
            raise ImplementationError(
                "User should not override the draw method.\n" +
                "He should implement_draw instead.")

        attr_to_set = self._parse_dict_params()
        for k in attr_to_set:
            if isinstance(self._dict_params[k], str):
                self._dict_params[k] = self._load_dict_from_file(
                    self._dict_params[k])
            setattr(
                self, k, self.__annotations__[k](
                    self._dict_params[k],
                    self._modeler,
                    self._name + "_" + k,
                    parent=self
                )
            )

        variations = {}
        for k, sub_dict in self._dict_params.items():
            splt = k.split("__")
            if len(splt) > 2:
                raise ValueError(
                    f"Variable {k} in config should " +
                    "contain maximum one '__'."
                )
            if len(splt) == 2 and splt[1].isdigit():
                variations
                self._create_variation(sub_dict, *splt)

    def _parse_dict_params(self) -> List[str]:
        attr_to_set = []
        for k, cls_name in self.__annotations__.items():
            if k in self._dict_params:
                if not issubclass(cls_name, DrawableElement):
                    self._set_element(k, self._dict_params[k])
                else:
                    attr_to_set.append(k)
            elif not k.startswith("_"):
                if not k.endswith("__dct"):
                    self._search_in_parents(k)
                else:
                    setattr(self, k, {})
        return attr_to_set

    def _set_element(self, key: str, value: Any) -> None:
        if key.endswith("__np") or self._mode == "None":
            setattr(self, key, value)
        elif key.endswith("__n") or self._mode == "gds":
            setattr(self, key, parse_entry(value))
        else:
            setattr(
                self,
                key,
                self._modeler.set_variable(
                    value, name=self.name + "_" + key))

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
        with open(file_path, 'r') as file:
            read = file.read()
            dict_par = yaml.safe_load(read)
        return dict_par

    def _create_variation(self, sub_dict, kv, indv):
        attr_dict = getattr(self, kv+"__dct", None)
        if attr_dict is None:
            raise ValueError(
                f"To have variation '{kv}__{indv}', the attribute" +
                f" '{kv}__dct' should be defined in class.")
        if sub_dict is not None:
            variation = deep_update(
                deepcopy(self._dict_params[kv]), sub_dict)
        attr_dict[indv] = self.__annotations__[kv](
            variation,
            self._modeler,
            self._name + f"_{kv}_{indv}",
            parent=self
        )

    @property
    def children(self) -> List:
        children = []
        for k in self.__dict__:
            if isinstance(self.__dict__[k], DrawableElement) and k != "parent":
                children.append(k)
        return children

    @property
    def parent(self):
        return self._parent

    @property
    def name(self):
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
            self._draw(body, **kwargs)


_T = TypeVar("_T", bound=DrawableElement)


class Variation(Generic[_T]):
    variation: Dict[int, _T]
    
    def __init__(self, variation: Dict[int, _T]):
        self._variations = variation

    def draw(self):
        for el in self.variations.values():
            el.draw()
