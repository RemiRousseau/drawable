from HFSSdrawpy import Modeler, Body
from example_class import Chip

pm = Modeler('gds')
body = Body(pm, 'chip')

chip = Chip(file_name="example/example_parameters.yaml",
            modeler=pm,
            name="chip")

chip.draw(body=body)
