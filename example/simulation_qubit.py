from HFSSdrawpy import Modeler, Body
from example_class import ChipDesign

pm = Modeler('hfss')
body = Body(pm, 'chip')

chip = ChipDesign(params="example/chip_params.yaml",
                  modeler=pm,
                  name="chip")

chip.draw(body=body)
