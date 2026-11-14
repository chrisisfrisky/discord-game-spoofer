using System;
using System.Windows.Forms;
// idle window that stays out of the way: off-screen, no taskbar button, never takes focus
class Quiet : Form {
    protected override bool ShowWithoutActivation { get { return true; } }
    protected override CreateParams CreateParams {
        get {
            var cp = base.CreateParams;
            cp.ExStyle |= 0x08000000 | 0x00000080; // WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW (no alt-tab / taskbar entry)
            return cp;
        }
    }
}
static class P {
    [STAThread] static void Main() {
        var f = new Quiet();
        f.Text = "idle";
        f.Width = 200; f.Height = 100;
        f.ShowInTaskbar = false;
        f.StartPosition = FormStartPosition.Manual;
        f.Location = new System.Drawing.Point(-32000, -32000);
        Application.Run(f);
    }
}
