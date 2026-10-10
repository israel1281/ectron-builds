using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Windows.Forms;

internal static class HostSetup
{
    private const string Brand = @BRAND@;
    private const string PayloadHash = @MSI_SHA256@;
    private const string PayloadName = @MSI_NAME@;

    [STAThread]
    private static int Main()
    {
        string directory = null;
        try
        {
            directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "Temp", Brand + "-host-setup-" + Guid.NewGuid().ToString("N"));
            var security = new DirectorySecurity();
            security.SetAccessRuleProtection(true, false);
            foreach (var sid in new[] { WellKnownSidType.LocalSystemSid, WellKnownSidType.BuiltinAdministratorsSid })
                security.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier(sid, null),
                    FileSystemRights.FullControl, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                    PropagationFlags.None, AccessControlType.Allow));
            Directory.CreateDirectory(directory, security);
            string package = Path.Combine(directory, PayloadName);
            using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("HostMsi"))
            using (var output = new FileStream(package, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                if (input == null) throw new InvalidDataException("The embedded host installer is missing.");
                input.CopyTo(output);
            }
            using (var input = File.OpenRead(package))
            using (var sha256 = SHA256.Create())
                if (BitConverter.ToString(sha256.ComputeHash(input)).Replace("-", "").ToLowerInvariant() != PayloadHash)
                    throw new InvalidDataException("The embedded host installer failed integrity verification.");

            var start = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "msiexec.exe"));
            start.Arguments = "/i \"" + package + "\" /qn /norestart CREATEDESKTOPSHORTCUTS=0 " +
                "STARTUPSHORTCUTS=0 LAUNCH_TRAY_APP=N /l*v \"" + Path.Combine(directory, "setup.log") + "\"";
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            int result;
            using (var process = Process.Start(start))
            {
                if (process == null) throw new InvalidOperationException("Windows Installer could not start.");
                process.WaitForExit();
                result = process.ExitCode;
            }
            if (result != 0 && result != 3010)
                throw new InvalidOperationException("Windows Installer returned error " + result + ".");
            foreach (var folder in new[] { Environment.SpecialFolder.DesktopDirectory,
                Environment.SpecialFolder.CommonDesktopDirectory })
                File.Delete(Path.Combine(Environment.GetFolderPath(folder), Brand + ".lnk"));
            foreach (var folder in new[] { Environment.SpecialFolder.Startup, Environment.SpecialFolder.CommonStartup })
                File.Delete(Path.Combine(Environment.GetFolderPath(folder), Brand + " Tray.lnk"));
            Directory.Delete(directory, true);
            return result;
        }
        catch (Exception error)
        {
            MessageBox.Show("Host setup did not complete.\n\n" + error.Message +
                (directory == null ? "" : "\n\nInstaller files and any log: " + directory),
                Brand + " host setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
