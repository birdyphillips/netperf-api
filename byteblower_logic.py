import subprocess
import os
from datetime import datetime
import time
from logger import Logger
from log_rotator import LogRotator
from config_loader import config

class ByteBlowerLogic:
    def __init__(self, bbp_file, scenario_name, bb_scenario_name, test_group_name=None, rtt_suffix="", report_formats="html pdf csv xls xlsx json docx"):
        self.logger = Logger("ByteBlowerLogic")
        self.bbp_file = bbp_file
        self.scenario_name = scenario_name
        self.bb_scenario_name = bb_scenario_name
        self.test_group_name = test_group_name
        self.rtt_suffix = rtt_suffix
        self.report_formats = report_formats
        self.test_id = int(datetime.now().timestamp())
        self.timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_prefix = f"{self.test_group_name}_{self.scenario_name}{self.rtt_suffix}_{self.timestamp_str}"
        self.log_file = f"logs/byteblower_{self.test_id}.log"
        self.log_rotator = LogRotator(self.log_file)
    
    def run_scenario(self, iteration, total_iterations, parent_output_dir=None):
        """Run ByteBlower CLI with specified scenario"""
        self.logger.info(f"Iteration {iteration + 1}/{total_iterations} - {self.scenario_name}{self.rtt_suffix}")
        
        # Create subfolder based on RTT value
        if parent_output_dir:
            if total_iterations > 1:
                scenario_dir = f"{self.scenario_name}{self.rtt_suffix}"
                output_dir = f"{parent_output_dir}/{scenario_dir}/iteration_{iteration + 1}/"
            else:
                output_dir = f"{parent_output_dir}/{self.scenario_name}/"
        else:
            if total_iterations > 1:
                output_dir = f"Results/{self.output_prefix}/iteration_{iteration + 1}/"
            else:
                output_dir = f"Results/{self.output_prefix}/"
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Handle bb_flows directory path
        if os.path.exists(self.bbp_file):
            project_path = self.bbp_file
        else:
            bb_flows_dir = config.byteblower_bb_flows_dir
            project_path = f"{bb_flows_dir}/{self.bbp_file}"
            
        cmd = [
            config.byteblower_cli_path,
            "--project", project_path,
            "--output", output_dir,
            "-scenario", self.bb_scenario_name
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            log_content = f"\n=== ByteBlower Iteration {iteration + 1} ===\n"
            log_content += f"Command: {' '.join(cmd)}\n"
            log_content += f"Return code: {result.returncode}\n"
            log_content += f"STDOUT:\n{result.stdout}\n"
            log_content += f"STDERR:\n{result.stderr}\n"
            self.log_rotator.write_log(log_content)
            
            if result.returncode != 0:
                self.logger.error(f"✗ ByteBlower failed: {result.stderr}")
                return False
            
            self._generate_additional_reports(output_dir)
            self._print_html_reports(output_dir)
            self.logger.info(f"✓ Iteration {iteration + 1} completed")
            
            # Wait 10 seconds between iterations (except after last iteration)
            if iteration < total_iterations - 1:
                time.sleep(10)
            
            return True
            
        except Exception as e:
            error_msg = f"ByteBlower execution exception: {str(e)}"
            self.logger.error(f"✗ {error_msg}")
            self.log_rotator.write_log(f"\nERROR: {error_msg}\n")
            return False
    
    def run_iterations(self, count=3, parent_output_dir=None):
        """Run multiple ByteBlower iterations"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"ByteBlower: {self.scenario_name}{self.rtt_suffix}")
        self.logger.info(f"Iterations: {count}")
        self.logger.info(f"{'='*60}")
        
        success_count = 0
        
        for i in range(count):
            if self.run_scenario(i, count, parent_output_dir):
                success_count += 1
            else:
                self.logger.error(f"✗ Iteration {i + 1} failed")
            
            if i < count - 1:
                time.sleep(10)
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"ByteBlower completed: {success_count}/{count} iterations successful")
        self.logger.info(f"{'='*60}\n")
        return success_count == count
    def _generate_additional_reports(self, output_dir):
        """Generate only R2 HTML report format with L4S column for TCP flows, keep JSON and CSV"""
        try:
            import shutil
            
            html_files = [f for f in os.listdir(output_dir) if f.endswith('.html') and '_R' not in f]
            if not html_files:
                return
            
            original_file = html_files[0]
            base_name = original_file.rsplit('.html', 1)[0]
            original_path = os.path.join(output_dir, original_file)
            
            r2_name = f"{base_name}_R2_1.html"
            r2_path = os.path.join(output_dir, r2_name)
            
            self._create_r2_report_with_l4s(original_path, r2_path)
            os.remove(original_path)
                
        except Exception as e:
            self.logger.error(f"Error generating R2 report: {str(e)}")
    
    def _create_r2_report_with_l4s(self, original_path, r2_path):
        """Create R2 report ensuring TCP flows have L4S column"""
        try:
            with open(original_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'TCP' in content and 'L4S' not in content:
                content = content.replace('<th>Flow Name</th>', '<th>Flow Name</th><th>L4S</th>')
                content = content.replace('TCP_', 'TCP_').replace('<td>TCP', '<td>TCP').replace('</td>', '</td><td>Yes/No</td>', 1)
            
            with open(r2_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        except Exception as e:
            self.logger.error(f"Error creating R2 report with L4S: {str(e)}")
            import shutil
            shutil.copy2(original_path, r2_path)
    
    def _print_html_reports(self, output_dir):
        """Print R2 HTML report and other file formats (JSON, CSV)"""
        try:
            html_files = [f for f in os.listdir(output_dir) if f.endswith('.html') and '_R2_' in f]
            json_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
            csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
            
            if html_files or json_files or csv_files:
                print(f"\n  Reports: ", end="")
                if html_files:
                    print(f"{len(html_files)} HTML ", end="")
                if json_files:
                    print(f"{len(json_files)} JSON ", end="")
                if csv_files:
                    print(f"{len(csv_files)} CSV", end="")
                print()
                
        except Exception as e:
            self.logger.error(f"Error listing reports: {str(e)}")
