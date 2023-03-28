from typing import Dict
from drawable.drawable_element import Design, DrawableElement
from HFSSdrawpy import Body, Entity
from HFSSdrawpy.parameters import TRACK, GAP, RLC
from HFSSdrawpy.utils import Vector


class Junction(DrawableElement):
    lj: str
    finger_width: str
    finger_gap: str
    finger_length: str
    connector_height: str
    ratio_finger_width__np: float
    margin: str
    undercut_width: str

    layer__np: int
    layer_undercut__np: int

    # Elements taken from parents
    pad_spacing: str

    def _draw(self, body: Body, **kwargs) -> None:
        h_gap = (self.finger_gap + self.finger_length)/2

        connector_l = self.pad_spacing/2 - h_gap

        if body.pm.mode == "hfss":
            positions = [[-connector_l-h_gap, -self.connector_height/2],
                         [h_gap, -self.connector_height/2]]
            dimensions = [[connector_l, self.connector_height],
                          [connector_l, self.connector_height]]
            names_ad = ["_left_con", "_right_con", ]
            for p, d, n in zip(positions, dimensions, names_ad):
                body.rect(p, d, name=self.name+n, layer=TRACK)

            jct = body.rect_center(
                [0, 0],
                [2*h_gap, self.connector_height],
                layer=RLC,
                name=self.name+"_jct"
            )
            points = [(-h_gap, 0), (h_gap, 0)]
            body.polyline(points, closed=False, name=self.name + "_line")
            jct.assign_lumped_RLC(
                points, (0, self.lj, 0))

            mesh_rect = body.rect_center(
                [0, 0],
                [2*self.pad_spacing,
                 self.connector_height],
                name=self.name+"_jct_mesh")
            mesh_rect.assign_mesh_length(self.connector_height/2)

        else:
            positions = [
                [-connector_l-h_gap, -self.connector_height/2],
                [-self.finger_width*self.ratio_finger_width__np-h_gap,
                 -self.finger_length - self.connector_height/2],
                [-h_gap + self.finger_gap,
                 -(self.connector_height + self.finger_length +
                   self.finger_width)/2],
                [h_gap, -self.connector_height/2],
                [h_gap, -self.connector_height/2 - self.finger_length]
            ]

            dimensions = [
                [connector_l, self.connector_height],
                [self.finger_width*self.ratio_finger_width__np,
                 self.finger_length],
                [self.finger_length, self.finger_width],
                [connector_l, self.connector_height],
                [self.connector_height, self.finger_length]]

            names_ad = ["_left_con", "_finger_down", "_figer_right",
                        "_right_con", "_right_bot_con"]

            marged_el = []
            marg_vect = Vector([self.margin]*2)

            for p, d, n in zip(positions, dimensions, names_ad):
                body.rect(p, d, name=self.name+n, layer=self.layer__np)
                marged_el.append(body.rect(
                    Vector(p)-marg_vect,
                    Vector(d)+2*marg_vect,
                    name=self.name+n+"_marged",
                    layer=self.layer_undercut__np))

            undercut_1 = body.rect(
                [-self.finger_width - h_gap - self.undercut_width,
                 -self.finger_length - self.connector_height/2 -
                 self.undercut_width],
                [2*self.undercut_width + self.finger_width,
                 self.undercut_width + self.finger_length +
                 self.connector_height],
                name=self.name+"_undercut_down",
                layer=self.layer_undercut__np)

            undercut_2 = body.rect(
                [-h_gap+self.finger_gap - self.undercut_width,
                 -(self.connector_height + self.finger_length +
                   self.finger_width)/2 - self.undercut_width],
                [self.finger_length + self.undercut_width-self.margin,
                 2*self.undercut_width+self.finger_width],
                name=self.name+"_undercut_right",
                layer=self.layer_undercut__np)
            undercut_1.unite(undercut_2)
            undercut_1.subtract(marged_el)


class CouplingPad(DrawableElement):
    dist: str
    offset: str

    # Elements taken from parents
    track: str
    gap: str
    pad_width: str
    pad_height: str
    pad_spacing: str

    def _draw(self, body: Body, **kwargs) -> None:
        with body([-self.pad_width/2 - self.dist,
                   -self.pad_spacing/2 - self.offset]):
            body.rect_center(
                [-self.track/2, -(self.pad_height - self.offset)/2],
                [self.track, self.pad_height - self.offset]
            )


class Transmon(DrawableElement):
    junction: Junction
    coupling_pad: CouplingPad
    pad_width: str
    pad_height: str
    pad_spacing: str

    cutout_width: str
    cutout_height: str

    # Elements taken from parents
    fillet: str

    def _draw(self, body: Body, **kwargs) -> None:
        with body([0, 0], [0, 1]):
            self.junction.draw(body=body, **kwargs)
        cutout = body.rect_center(
            [0, 0],
            [self.cutout_width, self.cutout_height],
            name=self.name+"_cutout",
            layer=GAP
        )
        cutout.fillet(self.fillet)
        for sign, n in zip([-1, 1], ["bot", "top"]):
            pad = body.rect_center(
                [0, sign*(self.pad_height + self.pad_spacing)/2],
                [self.pad_width, self.pad_height],
                name=self.name + f"_{n}_pad",
                layer=TRACK
            )
            pad.fillet(self.fillet)
        self.coupling_pad.draw(body=body, **kwargs)


class Readout(DrawableElement):
    height: str
    width: str

    # Elements taken from parents
    gap: str

    # Elements classined by _draw
    _gap: Entity
    _pad: Entity

    def _draw(self, body: Body, **kwargs) -> None:
        pass


class Qubit(DrawableElement):
    transmon: Transmon

    x_pos: str
    y_pos: str

    def _draw(self, body: Body, **kwargs):
        with body([self.x_pos, self.y_pos]):
            self.transmon.draw(body, **kwargs)


class Chip(Design):
    qubit: Qubit
    qubit__dct: Dict[int, Qubit]

    chip_width: str
    chip_height: str
    chip_thickness: str
    vacuum_thickness: str

    fillet: str
    track: str
    gap: str

    # Elements defined by _draw
    _ground_plane: Entity

    def _draw(self, body: Body, **kwargs):
        with body([self.chip_width/2, self.chip_height/2], [1, 0]):
            if len(self.qubit__dct) == 0:
                self.qubit.draw(body, **kwargs)
            else:
                for qbt in self.qubit__dct.values():
                    qbt.draw(body, **kwargs)

        self._ground_plane = body.rect(
            [0, 0], [self.chip_width, self.chip_height], layer=TRACK)
        gap_el = body.entities.get(GAP, None)
        if len(gap_el) >= 1:
            gap_el[0].unite(gap_el[1:])

        if gap_el is not None:
            self._ground_plane.subtract(gap_el)
        self._ground_plane.unite(body.entities[TRACK])
        self._ground_plane.assign_perfect_E()

        if body.pm.mode == 'gds':
            body.pm.generate_gds("example", self.name, max_points=199)

        if body.pm.mode == 'hfss':
            pos_sapphire = [0, 0, 0]
            size_sapphire = [self.chip_width,
                             self.chip_height,
                             -self.chip_thickness]
            body.box(pos_sapphire,
                     size_sapphire,
                     material='silicone',
                     name='substrate_0')
            pos_vac = [0, 0, 0]
            size_vac = [self.chip_width,
                        self.chip_height,
                        self.vacuum_thickness]
            vacuum = body.box(pos_vac,
                              size_vac,
                              material='vacuum',
                              name='top_box_0')
            pos_vac = [0, 0, -self.chip_thickness]
            size_vac = [self.chip_width,
                        self.chip_height,
                        -self.vacuum_thickness]
            vacuum.unite(body.box(pos_vac, size_vac, material='vacuum',
                                  name='top_box_1'))
