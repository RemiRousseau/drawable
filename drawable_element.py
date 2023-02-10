import yaml
from typing import List, Union

from HFSSdrawpy import Modeler, Body
from HFSSdrawpy.utils import parse_entry

class DrawableElement:
    parent = None
    name: str
    to_draw: bool = True

    def __init__(self, dict_params: dict, modeler: Modeler, name: str, parent = None) -> None:
        self.parent = parent
        attr_to_set = []
        self.name = name

        for k in self.__annotations__:
            if k in dict_params:
                if self.__annotations__[k] in [str, int]:
                    if k[-4:] == "__np":
                        setattr(self, k, dict_params[k])
                    elif k[-3:] == "__n" or modeler.mode=="gds":
                        setattr(self, k, parse_entry(dict_params[k]))
                    else:
                        setattr(
                            self, k, 
                            modeler.set_variable(dict_params[k], name=name + "_" + k))
                else:
                    attr_to_set.append(k)
            elif k not in ["parent", "name"]:
                while parent is not None:
                    if k in parent.__dict__:
                        setattr(self, k, parent.__dict__[k])
                        break
                    else:
                        if parent.parent is not None:
                            parent = parent.parent
                        else:
                            raise KeyError(f"Key {k} should be defined in .yaml file in {self.__class__.__name__} or it's parents.")
        for k in attr_to_set:
            setattr(self, k, self.__annotations__[k](dict_params[k], modeler, name + "_" + k, parent=self))
                
    
    def __repr__(self) -> str:
        string = ""
        for k in self.__annotations__:
            attr = getattr(self, k)
            repr_subel = repr(attr)
            if "\n" in repr_subel:
                repr_subel = repr_subel.replace("\n", "\n  ")
                string += f"{k}:\n  {repr_subel},\n"
            else:
                string += f"{k}: {repr_subel},\n"
        return f"{string[:-2]}"


    @property
    def children(self) -> List:
        return [k for k in self.__dict__ if (isinstance(self.__dict__[k], DrawableElement) and k!="parent")]
    

    def _draw(self, chip: Body, **kwargs) -> None:
        for k in self.children:
                attribute = getattr(self, k)
                attribute.draw(chip, **kwargs)
        if len(self.children)==0:
            raise NotImplementedError(f"_draw() of {self.__class__.__name__} is not implemented")


    def draw(self, chip: Body, **kwargs) -> None:
        if self.to_draw:
            return self._draw(chip, **kwargs)
        return None


class Design(DrawableElement):
    def __init__(self, file_name: str, modeler: Modeler, name: str) -> None:
        self.file_name = file_name
        with open(self.file_name, 'r') as file:
            read = file.read()
        dict_param = yaml.safe_load(read)
        super().__init__(dict_param, modeler, name)
