using System;
using System.Windows.Forms;
static class P {
    [STAThread] static void Main() {
        var f = new Form();
        f.Text = "idle";
        f.Width = 200; f.Height = 100;
        f.StartPosition = FormStartPosition.Manual; f.Location = new System.Drawing.Point(20, 20);
        Application.Run(f);
    }
}
