using System;
using System.Globalization;
using System.Drawing;
using System.IO;
using System.IO.Ports;
using System.Windows.Forms;
using System.Runtime.InteropServices;

class App : Form
{

    [DllImport("User32.dll")]
    public static extern short GetAsyncKeyState(Keys ArrowKeys);

    SerialPort port;
    double x = 100;
    double y = 100;


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
        this.DoubleBuffered = true;
        this.Text = "G Cam";
        this.TopMost = true;
        this.FormBorderStyle = FormBorderStyle.SizableToolWindow;
        this.ClientSize = new Size(75, 50);
        this.timer = new Timer()
        {
            Interval = 50,
            Enabled = true,
        };
        this.timer.Tick += this.HandleMovement;
        this.port = port;
        this.Home();
    }

    void HandleMovement(object sender, EventArgs ea)
    {
        int dir_x = 0;
        int dir_y = 0;

        if(this.Focused)
        {
            int speed = 1;
            if (GetAsyncKeyState(Keys.LShiftKey) < 0 || GetAsyncKeyState(Keys.RShiftKey) < 0)
                speed = 3;
            if (GetAsyncKeyState(Keys.Left) < 0)
                dir_x = -speed;
            if (GetAsyncKeyState(Keys.Right) < 0)
                dir_x = +speed;
            if (GetAsyncKeyState(Keys.Up) < 0)
                dir_y = +speed;
            if (GetAsyncKeyState(Keys.Down) < 0)
                dir_y = -speed;
        }

        if (dir_x != 0 || dir_y != 0)
        {
            this.RelativeMove(
                0.1 * dir_x,
                0.1 * dir_y
            );
        }
        this.Invalidate();
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
        var focus = this.Focused;
        ea.Graphics.Clear(focus ? Color.White : Color.Red);
        ea.Graphics.DrawString(
            string.Format("X = {0:F1}\r\nY = {1:F1}", this.x, this.y),
            this.Font,
            focus ? Brushes.Black : Brushes.White,
            10, 10
        );
    }

    protected override void OnKeyDown(KeyEventArgs ea)
    {
        switch (ea.KeyCode)
        {
            case Keys.H:
                this.Home();
                break;
            default:
                // Console.WriteLine("{0}", ea.KeyCode);
                break;
        }
    }
}