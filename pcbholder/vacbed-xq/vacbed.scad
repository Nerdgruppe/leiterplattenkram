


width = 110;
length = 80;
height = 10;

groove_size = 1;
groove_padding = 7;
groove_radius = 0.3;
groove_depth = 1.85;

grid_padding = 12;
grid_width = 1.5;
grid_spacing = 2.5;
grid_depth = 7;

grid_span = grid_spacing + grid_width;

hole_dia = 5;
hole_len = 2 * grid_padding + 1;

// computed

grid_wcnt = floor((width - 2 * grid_padding) / grid_span / 2);
grid_vcnt = floor((length - 2 * grid_padding) / grid_span / 2);

difference() {
  cube([width, length, height], true);

  translate([0, 0, height - grid_depth]) union() {
      for (x = [-grid_wcnt:1:grid_wcnt]) {
        translate([x * grid_span, 0, 0]) cube([grid_width, length - 2 * grid_padding, height], true);
      }
      for (y = [-grid_vcnt:1:grid_vcnt]) {
        translate([0, y * grid_span, 0]) cube([width - 2 * grid_padding, grid_width, height], true);
      }
    }

  minkowski() {

    translate([0, 0, height + groove_radius - groove_depth]) union() {

        translate([-width / 2 + groove_padding, 0, 0]) cube([groove_size - groove_radius, length - 2 * groove_padding, height], true);
        translate([width / 2 - groove_padding, 0, 0]) cube([groove_size - groove_radius, length - 2 * groove_padding, height], true);

        translate([0, -length / 2 + groove_padding, 0]) cube([width - 2 * groove_padding, groove_size - groove_radius, height], true);
        translate([0, length / 2 - groove_padding, 0]) cube([width - 2 * groove_padding, groove_size - groove_radius, height], true);
      }
    sphere(r=groove_radius, $fa=15, $fs=0.1);
  }

  translate([0,length/2,0])  rotate(90,[1,0,0]) cylinder(h=hole_len, d=hole_dia, $fa=15, $fs=0.1, center=true);
}
