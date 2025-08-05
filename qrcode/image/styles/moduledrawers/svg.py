import abc
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple

from qrcode.image.styles.moduledrawers.base import QRModuleDrawer
from qrcode.compat.etree import ET

if TYPE_CHECKING:
    from qrcode.image.svg import SvgFragmentImage, SvgPathImage
    from qrcode.main import ActiveWithNeighbors

ANTIALIASING_FACTOR = 4


class Coords(NamedTuple):
    x0: Decimal
    y0: Decimal
    x1: Decimal
    y1: Decimal
    xh: Decimal
    yh: Decimal


class BaseSvgQRModuleDrawer(QRModuleDrawer):
    trigger = True
    img: "SvgFragmentImage"
    
    def __init__(self, *, size_ratio: Decimal = Decimal(1), **kwargs):
        self.size_ratio = size_ratio
        self.trigger = True
       
    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.box_delta = (1 - self.size_ratio) * self.img.box_size / 2
        self.box_size = Decimal(self.img.box_size) * self.size_ratio
        self.box_half = self.box_size / 2
        
    def coords(self, box) -> Coords:
        row, col = box[0]
        x = row + self.box_delta
        y = col + self.box_delta

        return Coords(
            x,
            y,
            x + self.box_size,
            y + self.box_size,
            x + self.box_half,
            y + self.box_half,
        )


class SvgQRModuleDrawer(BaseSvgQRModuleDrawer):
    tag = "rect"

    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.tag_qname = ET.QName(self.img._SVG_namespace, self.tag)

    def drawrect(self, box, is_active: bool):
        if not is_active:
            return
        self.img._img.append(self.el(box))

    @abc.abstractmethod
    def el(self, box): ...


class SvgSquareDrawer(SvgQRModuleDrawer):
    def __init__(self, *, size_ratio = Decimal(1), color_tup=(0,0,0), **kwargs):
        super().__init__(size_ratio=size_ratio, **kwargs)
        self.color = color_tup

    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.unit_size = self.img.units(self.box_size)

    def el(self, box):
        coords = self.coords(box)
        return ET.Element(
            self.tag_qname,  # type: ignore
            x=self.img.units(coords.x0),
            y=self.img.units(coords.y0),
            width=self.unit_size,
            height=self.unit_size,
            fill=f"rgb{self.color}"
        )


class SvgCircleDrawer(SvgQRModuleDrawer):
    tag = "circle"
    def __init__(self, *, size_ratio = Decimal(1), color_tup=(0,0,0), **kwargs):
        super().__init__(size_ratio=size_ratio, **kwargs)
        self.color = color_tup


    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        self.radius = self.img.units(self.box_half)
    def el(self, box):
        coords = self.coords(box)
        return ET.Element(
            self.tag_qname,  # type: ignore
            cx=self.img.units(coords.xh),
            cy=self.img.units(coords.yh),
            r=self.radius,
            fill=f"rgb{self.color}"
        )


class SvgPathQRModuleDrawer(BaseSvgQRModuleDrawer):
    img: "SvgPathImage"

    def drawrect(self, box, is_active: bool):
        if not is_active:
            return
        self.img._subpaths.append(self.subpath(box))

    @abc.abstractmethod
    def subpath(self, box) -> str: ...


class SvgPathSquareDrawer(SvgPathQRModuleDrawer):
    def subpath(self, box) -> str:
        coords = self.coords(box)
        x0 = self.img.units(coords.x0, text=False)
        y0 = self.img.units(coords.y0, text=False)
        x1 = self.img.units(coords.x1, text=False)
        y1 = self.img.units(coords.y1, text=False)

        return f"M{x0},{y0}H{x1}V{y1}H{x0}z"


class SvgPathCircleDrawer(SvgPathQRModuleDrawer):
    # def __init__(self, *, size_ratio = Decimal(1), color_tup=(0,0,0), **kwargs):
    #     super().__init__(size_ratio=size_ratio, **kwargs)
    #     self.color = color_tup

    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)

    def subpath(self, box) -> str:
        coords = self.coords(box)
        x0 = self.img.units(coords.x0, text=False)
        yh = self.img.units(coords.yh, text=False)
        h = self.img.units(self.box_half - self.box_delta, text=False)
        x1 = self.img.units(coords.x1, text=False)

        # rx,ry is the centerpoint of the arc
        # 1? is the x-axis-rotation
        # 2? is the large-arc-flag
        # 3? is the sweep flag
        # x,y is the point the arc is drawn to

        return f"M{x0},{yh}A{h},{h} 0 0 0 {x1},{yh}A{h},{h} 0 0 0 {x0},{yh}z"


### CUSTOM IMPLEMENTATIONS

class SvgGappedSquareDrawer(SvgSquareDrawer):
    """
    Draws square modules with gaps between them.
    The size_ratio determines how wide the squares are relative to the grid spacing.
    """

    def __init__(self, *, size_ratio: float = 0.8, color_tup=(0,0,0), **kwargs):
        """
        Args:
            size_ratio: Size of squares relative to grid (0-1)
                       0.8 = 80% square with 20% gap
                       0.5 = 50% square with 50% gap
        """
        # Just pass the size_ratio to parent - it handles everything!
        super().__init__(size_ratio=Decimal(size_ratio), color_tup=color_tup, **kwargs)


class SvgHorizontalBarsDrawer(SvgQRModuleDrawer):
    needs_neighbors = True
    
    def __init__(self, *, size_ratio=Decimal(1), color_tup=(0,0,0), vertical_shrink=0.8, **kwargs):
        super().__init__(size_ratio=size_ratio, **kwargs)
        self.color = color_tup
        self.vertical_shrink = Decimal(str(vertical_shrink))
        
    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        
    def el(self, box):
        SCALE_CORRECTION = Decimal(2.645)
        coords = self.coords(box)
        
        # Calculate vertical inset (gap on top/bottom)
        v_delta = (Decimal(1) - self.vertical_shrink) * (coords.y1 - coords.y0) / 2
        
        # Adjusted coordinates with vertical shrinking
        x0 = coords.x0 / SCALE_CORRECTION
        x1 = coords.x1 / SCALE_CORRECTION
        y0 = (coords.y0 + v_delta) / SCALE_CORRECTION
        y1 = (coords.y1 - v_delta) / SCALE_CORRECTION
        
        # Radius for rounded ends (half the bar height)X
        radius = (y1 - y0) / 2 
        
        # Get module position
        border_modules = self.img.border
        (px0, py0), (px1, py1) = box
        row = int(py0 / self.img.box_size) - border_modules
        col = int(px0 / self.img.box_size) - border_modules
        
        modules = self.img.modules
        
        def is_active(row, col):
            if 0 <= row < len(modules) and 0 <= col < len(modules[0]):
                return bool(modules[row][col])
            return False
        
        # Check west and east neighbors
        has_west = is_active(row, col - 1)
        has_east = is_active(row, col + 1)
        
        # Build path based on neighbors
        if not has_west and not has_east:
    # Isolated module - pill shape (horizontal)
            path = f"M {x0 + radius} {y0} \
                    L {x1 - radius} {y0} \
                    A {radius} {radius} 0 0 1 {x1} {y0 + radius} \
                    L {x1} {y1 - radius} \
                    A {radius} {radius} 0 0 1 {x1 - radius} {y1} \
                    L {x0 + radius} {y1} \
                    A {radius} {radius} 0 0 1 {x0} {y1 - radius} \
                    L {x0} {y0 + radius} \
                    A {radius} {radius} 0 0 1 {x0 + radius} {y0} \
                    Z"
        elif has_west and not has_east:
            # Connected left, rounded right
            path = f"M {x0} {y0} \
                    L {x1 - radius} {y0} \
                    A {radius} {radius} 0 0 1 {x1 - radius} {y1} \
                    L {x0} {y1} \
                    Z"
        elif not has_west and has_east:
            # Rounded left, connected right
            path = f"M {x0 + radius} {y0} \
                    L {x1} {y0} \
                    L {x1} {y1} \
                    L {x0 + radius} {y1} \
                    A {radius} {radius} 0 0 1 {x0 + radius} {y0} \
                    Z"
        else:
            # Connected both ends - simple rectangle
            path = f"M {x0} {y0} \
                    L {x1} {y0} \
                    L {x1} {y1} \
                    L {x0} {y1} \
                    Z"
        
        return ET.Element(
            "path",
            d=path,
            fill=f"rgb{self.color}"
        )   


class SvgVerticalBarsDrawer(SvgQRModuleDrawer):
    needs_neighbors = True
    
    def __init__(self, *, size_ratio=Decimal(1), color_tup=(0,0,0), horizontal_shrink=0.8, **kwargs):
        super().__init__(size_ratio=size_ratio, **kwargs)
        self.color = color_tup
        self.horizontal_shrink = horizontal_shrink
        
    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)
        
    def el(self, box):
        SCALE_CORRECTION = Decimal(2.645)
        coords = self.coords(box)
        
        # Calculate horizontal inset (gap on sides)
        h_delta = (1 - Decimal(self.horizontal_shrink)) * (coords.x1 - coords.x0) / 2
        
        # Adjusted coordinates with horizontal shrinking
        x0 = (coords.x0 + h_delta) / SCALE_CORRECTION
        x1 = (coords.x1 - h_delta) / SCALE_CORRECTION
        y0 = coords.y0 / SCALE_CORRECTION
        y1 = coords.y1 / SCALE_CORRECTION
        
        # Radius for rounded ends (half the bar width)
        radius = (x1 - x0) / 2
        
        # Get module position
        border_modules = self.img.border
        (px0, py0), (px1, py1) = box
        row = int(py0 / self.img.box_size) - border_modules
        col = int(px0 / self.img.box_size) - border_modules
        
        modules = self.img.modules
        
        def is_active(row, col):
            if 0 <= row < len(modules) and 0 <= col < len(modules[0]):
                return bool(modules[row][col])
            return False
        
        # Check north and south neighbors
        has_north = is_active(row - 1, col)
        has_south = is_active(row + 1, col)
        
        # Build path based on neighbors
        if not has_north and not has_south:
            # Isolated module - pill shape
            path = f"M {x0} {y0 + radius} \
                    A {radius} {radius} 0 0 1 {x1} {y0 + radius} \
                    L {x1} {y1 - radius} \
                    A {radius} {radius} 0 0 1 {x0} {y1 - radius} \
                    Z"
        elif has_north and not has_south:
            # Connected top, rounded bottom
            path = f"M {x0} {y0} \
                    L {x1} {y0} \
                    L {x1} {y1 - radius} \
                    A {radius} {radius} 0 0 1 {x0} {y1 - radius} \
                    Z"
        elif not has_north and has_south:
            # Rounded top, connected bottom
            path = f"M {x0} {y0 + radius} \
                    A {radius} {radius} 0 0 1 {x1} {y0 + radius} \
                    L {x1} {y1} \
                    L {x0} {y1} \
                    Z"
        else:
            # Connected both ends - simple rectangle
            path = f"M {x0} {y0} \
                    L {x1} {y0} \
                    L {x1} {y1} \
                    L {x0} {y1} \
                    Z"
        
        return ET.Element(
            "path",
            d=path,
            fill=f"rgb{self.color}"
        )


class SvgRoundedDrawer(SvgQRModuleDrawer):

    needs_neighbors = True


    def __init__(self, *, size_ratio = Decimal(1), color_tup=(0,0,0), round_radius=3, **kwargs):
        super().__init__(size_ratio=size_ratio, **kwargs)
        self.color = color_tup
        self.radius = round_radius
        

    def initialize(self, *args, **kwargs) -> None:
        super().initialize(*args, **kwargs)

    def build_dynamic_path(self, top_left, top_right, bottom_right, bottom_left, 
                      round_tl, round_tr, round_br, round_bl):
        """
        Build SVG path with any combination of rounded corners.
        Goes clockwise: top-left → top-right → bottom-right → bottom-left → close
        """
        path = []
        if round_tl:
            path.append(f"M {top_left[0]} {top_left[1] + self.radius} ")
            path.append(f"Q {top_left[0]} {top_left[1]} {top_left[0] + self.radius} {top_left[1]}")
        else:
            path.append(f"M {top_left[0]} {top_left[1]}")
        
        if round_tr:
            path.append(f"L {top_right[0] - self.radius} {top_right[1]} ")
            path.append(f"Q {top_right[0]} {top_right[1]} {top_right[0]} {top_right[1] + self.radius}")
        else:
            path.append(f"L {top_right[0]} {top_right[1]}")
        
        if round_br:
            path.append(f"L {bottom_right[0]} {bottom_right[1] - self.radius} ")
            path.append(f"Q {bottom_right[0]} {bottom_right[1]} {bottom_right[0] - self.radius} {bottom_right[1]}")
        else:
            path.append(f"L {bottom_right[0]} {bottom_right[1]}")
        
        if round_bl:
            path.append(f"L {bottom_left[0] + self.radius} {bottom_left[1]} ")
            path.append(f"Q {bottom_left[0]} {bottom_left[1]} {bottom_left[0]} {bottom_left[1] - self.radius}")
        else:
            path.append(f"L {bottom_left[0]} {bottom_left[1]}")
        path.append("Z")
        return " ".join(path)

    def el(self, box):

        SCALE_CORRECTION = Decimal(2.645)
        coords = self.coords(box)
        top_left = (coords.x0 / SCALE_CORRECTION, coords.y0 / SCALE_CORRECTION)
        bottom_right = (coords.x1/ SCALE_CORRECTION, coords.y1 / SCALE_CORRECTION)
        top_right = (coords.x1/ SCALE_CORRECTION, coords.y0 / SCALE_CORRECTION)
        bottom_left = (coords.x0/ SCALE_CORRECTION, coords.y1 / SCALE_CORRECTION)


        top_left_rounded = f"M {top_left[0]} {top_left[1] + self.radius} \
        Q {top_left[0]} {top_left[1]} {top_left[0] + self.radius} {top_left[1]} \
        L {top_right[0]} {top_right[1]} \
        L {bottom_right[0]} {bottom_right[1]} \
        L {bottom_left[0]} {bottom_left[1]} \
        Z"


        # top_right_rounded = f"M {top_left[0]} {top_left[1]} \
        # L {top_right[0] - self.radius} {top_right[1]} \
        # Q {top_right[0]} {top_right[1]} {top_right[0]} {top_right[1] + self.radius} \
        # L {bottom_right[0]} {bottom_right[1]} \
        # L {bottom_left[0]} {bottom_left[1]} \
        # Z"
        # bottom_right_rounded = f"M {top_left[0]} {top_left[1]} \
        # L {top_right[0]} {top_right[1]} \
        # L {bottom_right[0]} {bottom_right[1] - self.radius} \
        # Q {bottom_right[0]} {bottom_right[1]} {bottom_right[0] - self.radius} {bottom_right[1]} \
        # L {bottom_left[0]} {bottom_left[1]} \
        # Z"
        # bottom_left_rounded = f"M {top_left[0]} {top_left[1]} \
        # L {top_right[0]} {top_right[1]} \
        # L {bottom_right[0]} {bottom_right[1]} \
        # L {bottom_left[0] + self.radius} {bottom_left[1]} \
        # Q {bottom_left[0]} {bottom_left[1]} {bottom_left[0]} {bottom_left[1] - self.radius} \
        # Z"
        # default_module = f"M {top_left[0]} {top_left[1]} \
        # L {top_right[0]} {top_right[1]} \
        # L {bottom_right[0]} {bottom_right[1]} \
        # L {bottom_left[0]} {bottom_left[1]} \
        # Z"
        # all_rounded = f"M {top_left[0]} {top_left[1] + self.radius} \
        #     Q {top_left[0]} {top_left[1]} {top_left[0] + self.radius} {top_left[1]} \
        #     L {top_right[0] - self.radius} {top_right[1]}  \
        #     Q {top_right[0]} {top_right[1]} {top_right[0]} {top_right[1] + self.radius} \
        #     L {bottom_right[0]} {bottom_right[1] - self.radius} \
        #     Q {bottom_right[0]} {bottom_right[1]} {bottom_right[0] - self.radius} {bottom_right[1]} \
        #     L {bottom_left[0] + self.radius} {bottom_left[1]} \
        #     Q {bottom_left[0]} {bottom_left[1]} {bottom_left[0]} {bottom_left[1] - self.radius} \
        #     Z"
        border_modules = self.img.border

        (x0, y0), (x1, y1) = box

        modules = self.img.modules

        #Mapping coordinates to modules indexes
        row= int(y0 / self.img.box_size) - border_modules
        col = int(x0 / self.img.box_size) - border_modules

        def is_active(row, col):
            if 0 <= row < len(modules) and 0 <= col < len(modules[0]):  # Changed r,c to row,col
                return bool(modules[row][col])
            return False

        n  = is_active(row - 1, col)      # North
        ne = is_active(row - 1, col + 1)  # Northeast  
        e  = is_active(row, col + 1)      # East
        se = is_active(row + 1, col + 1)  # Southeast
        s  = is_active(row + 1, col)      # South
        sw = is_active(row + 1, col - 1)  # Southwest
        w  = is_active(row, col - 1)      # West
        nw = is_active(row - 1, col - 1)  # Northwest

        
        round_tl = not (n or w )  # If need diagonal check - add nw,ne,se and so on
        round_tr = not (n or e )
        round_br = not (s or e )
        round_bl = not (s or w )

        d = self.build_dynamic_path(top_left, top_right, bottom_right, bottom_left, round_tl, round_tr, round_br, round_bl)

        return ET.Element(
            "path",
            d=d,
            fill=f"rgb{self.color}"
        )


class SvgPathGappedSquareDrawer(SvgPathSquareDrawer):
    """
    Draws square modules with gaps between them.
    The size_ratio determines how wide the squares are relative to the grid spacing.
    """
    
    def __init__(self, *, size_ratio: float = 0.8, **kwargs):
        """
        Args:
            size_ratio: Size of squares relative to grid (0-1)
                       0.8 = 80% square with 20% gap
                       0.5 = 50% square with 50% gap
        """
        # Just pass the size_ratio to parent - it handles everything!
        super().__init__(size_ratio=Decimal(size_ratio), **kwargs)


class SvgPathVerticalBarsDrawer(SvgPathQRModuleDrawer):
    """
    Draws vertically contiguous modules as continuous bars with rounded ends.
    Horizontal gaps controlled by horizontal_shrink parameter.
    """
    
    needs_neighbors = True
    
    def __init__(self, *, horizontal_shrink: float = 0.8, **kwargs):
        super().__init__(**kwargs)
        self.horizontal_shrink = horizontal_shrink
    
    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        # Calculate horizontal inset (gap on sides)
        self.h_delta = Decimal(1 - self.horizontal_shrink) * self.box_size / 2
    
    def drawrect(self, box, is_active):
        if not is_active:
            return
        self._neighbors = is_active
        self.img._subpaths.append(self.subpath(box))
    
    def subpath(self, box) -> str:
        coords = self.coords(box)
        
        # Apply horizontal shrinking
        x0 = self.img.units(coords.x0 + self.h_delta, text=False)
        x1 = self.img.units(coords.x1 - self.h_delta, text=False)
        y0 = self.img.units(coords.y0, text=False)
        y1 = self.img.units(coords.y1, text=False)
        
        # Calculate radius for rounded ends (half the bar width)
        r = self.img.units((coords.x1 - coords.x0 - 2 * self.h_delta) / 2, text=False)
        
        # Check neighbors
        has_top = getattr(self._neighbors, 'N', False) if hasattr(self, '_neighbors') else False
        has_bottom = getattr(self._neighbors, 'S', False) if hasattr(self, '_neighbors') else False
        
        # Build path
        if not has_top and not has_bottom:
            # Isolated module - draw a rounded rectangle (pill shape)
            return (f"M{x0},{y0+r}"
                   f"A{r},{r} 0 0 1 {x1},{y0+r}"
                   f"V{y1-r}"
                   f"A{r},{r} 0 0 1 {x0},{y1-r}"
                   f"z")
        elif has_top and not has_bottom:
            # Connected top, rounded bottom
            return (f"M{x0},{y0}"
                   f"H{x1}"
                   f"V{y1-r}"
                   f"A{r},{r} 0 0 1 {x0},{y1-r}"
                   f"z")
        elif not has_top and has_bottom:
            # Rounded top, connected bottom
            return (f"M{x0},{y0+r}"
                   f"A{r},{r} 0 0 1 {x1},{y0+r}"
                   f"V{y1}"
                   f"H{x0}"
                   f"z")
        else:
            # Connected both ends - simple rectangle
            return f"M{x0},{y0}H{x1}V{y1}H{x0}z"


class SvgPathHorizontalBarsDrawer(SvgPathQRModuleDrawer):
    """
    Draws horizontally contiguous modules as continuous bars with rounded ends.
    Vertical gaps controlled by vertical_shrink parameter.
    """
    
    needs_neighbors = True
    
    def __init__(self, *, vertical_shrink: float = 0.8, **kwargs):
        super().__init__(**kwargs)
        self.vertical_shrink = vertical_shrink
    
    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        # Calculate vertical inset (gap on top/bottom)
        self.v_delta = Decimal(1 - self.vertical_shrink) * self.box_size / 2
    
    def drawrect(self, box, is_active):
        if not is_active:
            return
        self._neighbors = is_active
        self.img._subpaths.append(self.subpath(box))
    
    def subpath(self, box) -> str:
        coords = self.coords(box)
        
        # Apply vertical shrinking
        x0 = self.img.units(coords.x0, text=False)
        x1 = self.img.units(coords.x1, text=False)
        y0 = self.img.units(coords.y0 + self.v_delta, text=False)
        y1 = self.img.units(coords.y1 - self.v_delta, text=False)
        
        # Calculate radius for rounded ends (half the bar height)
        r = self.img.units((coords.y1 - coords.y0 - 2 * self.v_delta) / 2, text=False)
        
        # Check neighbors
        has_left = getattr(self._neighbors, 'W', False) if hasattr(self, '_neighbors') else False
        has_right = getattr(self._neighbors, 'E', False) if hasattr(self, '_neighbors') else False
        
        # Build path
        if not has_left and not has_right:
            # Isolated module - draw a rounded rectangle (pill shape)
            return (f"M{x0+r},{y0}"
                   f"H{x1-r}"
                   f"A{r},{r} 0 0 1 {x1},{y1}"
                   f"H{x0+r}"
                   f"A{r},{r} 0 0 1 {x0},{y0}"
                   f"z")
        elif has_left and not has_right:
            # Connected left, rounded right
            return (f"M{x0},{y0}"
                   f"H{x1-r}"
                   f"A{r},{r} 0 0 1 {x1},{y1}"
                   f"H{x0}"
                   f"z")
        elif not has_left and has_right:
            # Rounded left, connected right
            return (f"M{x0+r},{y0}"
                   f"H{x1}"
                   f"V{y1}"
                   f"H{x0+r}"
                   f"A{r},{r} 0 0 1 {x0},{y0}"
                   f"z")
        else:
            # Connected both ends - simple rectangle
            return f"M{x0},{y0}H{x1}V{y1}H{x0}z"


class SvgPathRoundedDrawer(SvgPathQRModuleDrawer):
    """Draws rounded square modules, only rounding actual corners."""
    
    needs_neighbors = True
    
    def __init__(self, *, radius_ratio: float = 0.5, **kwargs):
        super().__init__(**kwargs)
        self.radius_ratio = min(1, max(0, radius_ratio))
    
    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        self.corner_radius = self.box_half * Decimal(self.radius_ratio)
    
    def drawrect(self, box, is_active):
        if not is_active:
            return
        self._neighbors = is_active  # Store for subpath
        self.img._subpaths.append(self.subpath(box))
    
    def subpath(self, box) -> str:
        coords = self.coords(box)
        x0, y0 = self.img.units(coords.x0, text=False), self.img.units(coords.y0, text=False)
        x1, y1 = self.img.units(coords.x1, text=False), self.img.units(coords.y1, text=False)
        r = self.img.units(self.corner_radius, text=False)
        
        # Check corners (only round if no neighbors in both directions)
        n = getattr(self._neighbors, 'N', False) if hasattr(self, '_neighbors') else False
        s = getattr(self._neighbors, 'S', False) if hasattr(self, '_neighbors') else False
        e = getattr(self._neighbors, 'E', False) if hasattr(self, '_neighbors') else False
        w = getattr(self._neighbors, 'W', False) if hasattr(self, '_neighbors') else False
        
        nw, ne = not (w or n), not (n or e)
        se, sw = not (e or s), not (s or w)
        
        # Simple square if no rounding
        if not any([nw, ne, se, sw]) or r == "0":
            return f"M{x0},{y0}H{x1}V{y1}H{x0}z"
        
        # Build path with selective rounding
        path = f"M{x0},{y0+r if nw else y0}"
        if nw: path += f"A{r},{r} 0 0 1 {x0+r},{y0}H{x1-r if ne else x1}"
        else: path += f"H{x1-r if ne else x1}"
        if ne: path += f"A{r},{r} 0 0 1 {x1},{y0+r}V{y1-r if se else y1}"
        else: path += f"V{y1-r if se else y1}"
        if se: path += f"A{r},{r} 0 0 1 {x1-r},{y1}H{x0+r if sw else x0}"
        else: path += f"H{x0+r if sw else x0}"
        if sw: path += f"A{r},{r} 0 0 1 {x0},{y1-r}"
        path += "z"
        
        return path