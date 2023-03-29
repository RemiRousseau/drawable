from HFSSdrawpy import Modeler, Body
from example_class import Chip

pm = Modeler('hfss')
body = Body(pm, 'chip')

chip = Chip(params="example/chip_params.yaml",
            modeler=pm,
            name="chip")

chip.draw(body=body)
