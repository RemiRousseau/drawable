from HFSSdrawpy import Modeler, Body
from example_class import Chip

pm = Modeler('gds')
body = Body(pm, 'chip')

chip = Chip(
    folder="example/yaml_files",
    params="chip_params.yaml",
    modeler=pm,
    name="chip"
)

chip.draw(body=body)
