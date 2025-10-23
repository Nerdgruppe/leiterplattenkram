
dev_length = 130;
dev_width = 85;

pcb_length = 100;
pcb_width = 70;
pcb_height = 1.7;

screw_hole = 5.5; // M5
banana_hole = 4.3; // M4

pcb_padding = 5; // inner margin
pcb_margin = 4; // outer margin

pcb_spacing = 1.5; // vertical spacing

fin_length = 35;
fin_width = 0.5;
fin_count = 9;
fin_spacing = 3.0;

dev_height = 2 * pcb_height + pcb_spacing;

flowchan_height = pcb_spacing;
connect_width = 3.0;

module inflow_shape(rounder_height) {
    difference() {
  union() {
    translate([-dev_width / 2, 0, 0]) cylinder(rounder_height, d=dev_width, center=true);
    translate([-dev_width / 4, 0, 0]) cube([dev_width / 2, dev_width, rounder_height], true);
  }

    translate([-dev_width / 4, dev_width/2 - screw_hole, 0]) cylinder(200, d=screw_hole, center=true);
    translate([-dev_width / 4, -dev_width/2 + screw_hole, 0]) cylinder(200, d=screw_hole, center=true);
    translate([-dev_width + screw_hole, 0, 0]) cylinder(200, d=screw_hole, center=true);
    }
}

module body() {

  $fs = 1.0;

  difference() {
    cube([dev_length, dev_width, dev_height], true); // base body

    cube([pcb_length - pcb_padding, pcb_width - pcb_padding, 20], true); // pcb hole

    translate([0, 0, (5 + pcb_spacing) / 2]) cube([pcb_length + pcb_margin, pcb_width + pcb_margin, 5], true); // top pcb insert
    translate([0, 0, -(5 + pcb_spacing) / 2]) cube([pcb_length + pcb_margin, pcb_width + pcb_margin, 5], true); // bottom pcb insert

    translate([0, (pcb_width + pcb_margin - connect_width) / 2, (5 + pcb_spacing) / 2]) cube([2 * dev_length, connect_width, 5], true); // top pcb insert
    translate([0, -(pcb_width + pcb_margin - connect_width) / 2, -(5 + pcb_spacing) / 2]) cube([2 * dev_length, connect_width, 5], true); // bottom pcb insert

    cube([dev_length + 10, pcb_width - pcb_padding, pcb_spacing], true); // flow channel

    // screw holes for 
    union() {
      for (px = [-1:2:1])
        for (py = [-1:2:1]) {
          {
            translate([(pcb_length - 2 * screw_hole + 2) * px / 2, (pcb_width + 2 * screw_hole + 2) * py / 2, 0]) cylinder(20, d=screw_hole, center=true);
          }
        }
    }
  }

  con_size = (dev_length - pcb_length - pcb_margin) / 2;

  for (py = [-1:2:1]) {
    translate([dev_length / 2 + con_size / 2, py * (pcb_width - pcb_padding) / 2 + py * con_size / 2, 0]) difference() {
        cube([con_size, con_size, pcb_spacing], true);
        cylinder(20, d=banana_hole, center=true);
      }
  }

  rounder_height = dev_height - pcb_spacing;

  translate([-dev_length / 2, 0, -pcb_spacing / 2]) {

    difference() {
      inflow_shape(rounder_height);
      union() {
        translate([-dev_width / 2, 0, pcb_height]) cylinder(2 * pcb_height, d=pcb_width - pcb_padding, center=true);
        translate([-dev_width / 4, 0, pcb_height + rounder_height / 2]) cube([dev_width / 2, pcb_width - pcb_padding, 2 * rounder_height], true);
      }
    }

    for (i = [-fin_count:fin_count]) {
      translate([(dev_length - pcb_length - pcb_margin) / 2 - fin_length, fin_spacing * i, 0]) cube([fin_length, fin_width, flowchan_height]);
    }
  }
}

module sucky_nozzle() {

  union() {
    for (i = [0:3]) {
      translate([0, 0, 4 * i]) cylinder(5, d1=5.5, d2=3.5, center=true);
    }
  }
}

module inflow_cap() {
  $fs = 1.0;
  difference() {
    union() {
      inflow_shape(2.0);
      translate([-dev_width / 2, 0, 3]) sucky_nozzle();
    }

    translate([-dev_width / 2, 0, 0]) cylinder(200, d=3.0, center=true);

  }
}

body();

// translate([0, 100, 0])
//  inflow_cap();
