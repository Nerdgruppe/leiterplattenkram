using System;
using System.Globalization;
using System.Drawing;
using System.IO;
using System.IO.Ports;
using System.Windows.Forms;

class App : Form
{
    SerialPort port;
    double x = 100;
    double y = 100;

    int dir_x = 0;
    int dir_y = 0;

    Timer timer;

    public static void Main(string[] args)
    {
        using (var port = new SerialPort("COM7", 115200))
        {
            port.Open();
            Application.Run(new App(port));
        }
    }

    App(SerialPort port)
    {
        this.Text = "G Cam";
        this.TopMost = true;
        this.FormBorderStyle = FormBorderStyle.SizableToolWindow;
        this.timer = new Timer()
        {
            Interval = 100,
            Enabled = true,
        };
        this.timer.Tick += this.HandleMovement;
        this.port = port;
        this.Home();
    }

    void HandleMovement(object sender, EventArgs ea)
    {
        if(this.dir_x != 0 || this.dir_y != 0)
        {
            this.RelativeMove(
                0.25 * this.dir_x,
                0.25 * this.dir_y
            );
        }
    }

    void Home()
    {
        this.x = 100;
        this.y = 100;
        this.MoveTo(this.x, this.y);
    }

    void RelativeMove(double dx, double dy)
    {
        this.x += dx;
        this.y += dy;
        this.MoveTo(this.x, this.y);
    }

    void MoveTo(double x, double y)
    {
        var cmd = string.Format(CultureInfo.InvariantCulture, "G0 X{0:F1} Y{1:F1} F3000\r\n", x, y);
        Console.WriteLine(cmd);
        port.Write(cmd);
        this.x = x;
        this.y = y;
        this.Invalidate();
    }

    protected override void OnPaint(PaintEventArgs ea)
    {
        ea.Graphics.Clear(Color.White);
        ea.Graphics.DrawString(
            string.Format("X = {0:F1}\r\nY = {1:F1}", this.x, this.y),
            this.Font,
            Brushes.Black,
            10, 10
        );
    }

    protected override void OnKeyDown(KeyEventArgs ea)
    {
        switch (ea.KeyCode)
        {
            case Keys.Escape:
                this.dir_x = 0;
                this.dir_y = 0;
                break;
            case Keys.H:
                this.Home();
                break;
            case Keys.Up:
                this.dir_y = 1;
                break;
            case Keys.Down:
                this.dir_y = -1;
                break;
            case Keys.Left:
                this.dir_x = -1;
                break;
            case Keys.Right:
                this.dir_x = 1;
                break;
            case Keys.OemMinus:
                // TODO: Move Z Down
                break;
            case Keys.Oemplus:
                // TODO: Move Z Up
                break;
            default:
                Console.WriteLine("{0}", ea.KeyCode);
                break;
        }
    }
    
    protected override void OnKeyUp(KeyEventArgs ea)
    {
        switch (ea.KeyCode)
        {
            case Keys.Up:
            case Keys.Down:
                this.dir_y = 0;
                break;
            case Keys.Left:
            case Keys.Right:
                this.dir_x = 0;
                break;
            default:
                Console.WriteLine("{0}", ea.KeyCode);
                break;
        }
    }
}