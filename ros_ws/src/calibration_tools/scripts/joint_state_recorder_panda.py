import time
import rospy
import numpy as np
from std_msgs.msg import Float32
from geometry_msgs.msg import PoseStamped
from joint_state_recorder import JointStatesRecorder
import panda_py
import dynamic_reconfigure.client

class JointStatesRecorderPanda(JointStatesRecorder):
    def __init__(self, joint_state_topic_name: str, folder_name: str, config: dict):
        super().__init__(joint_state_topic_name, folder_name, 7)
        self._pykeyboard.stop()
        hostname = config['hostname']
        username = config['username']
        password = config['password']
        self.desk = panda_py.Desk(hostname, username, password)
        self.desk.listen(self._on_press_panda)
        self.desk._listening = True
        self.vibration_pub = rospy.Publisher("/haptic_feedback", Float32, queue_size=0)
        self.pose_subsciber = rospy.Subscriber("/cartesian_pose", PoseStamped, self._pose_callback)
        self._last_time_pressed = rospy.Time.now()
        self._pose = np.zeros(7)
        self.set_K = dynamic_reconfigure.client.Client('/dynamic_reconfigure_compliance_param_node', config_callback=None)
        self.set_K.update_configuration({"translational_stiffness_X": 0})
        self.set_K.update_configuration({"translational_stiffness_Y": 0})
        self.set_K.update_configuration({"translational_stiffness_Z": 0})
        self.set_K.update_configuration({"rotational_stiffness_X": 0}) 
        self.set_K.update_configuration({"rotational_stiffness_Y": 0}) 
        self.set_K.update_configuration({"rotational_stiffness_Z": 0})

    def _pose_callback(self, pose: PoseStamped) -> None:
        self._pose = np.array([
                pose.pose.position.x, 
                pose.pose.position.y, 
                pose.pose.position.z, 
                pose.pose.orientation.w, 
                pose.pose.orientation.x, 
                pose.pose.orientation.y, 
                pose.pose.orientation.z, 
        ])

    def vibrate(self, duration=0.2):
        self.vibration_pub.publish(Float32(data=duration))

    def _on_press_panda(self, event: dict) -> None:
        time_since_last_press = (rospy.Time.now() - self._last_time_pressed).to_sec()
        if time_since_last_press < 0.6:
            return
        self._last_time_pressed = rospy.Time.now()
        
        if 'check' in event and event['check']: 
            self._data[self.hole_name()].append(self._positions)
            self._data[f"{self.hole_name()}_pose"].append(self._pose)


            self.log(f"Addded data point for {self.hole_name()} with value {self._positions}")
            if len(self._data[self.hole_name()]) >= 30:
                self.vibrate(duration=0.5)
                print('test')
            else:
                self.vibrate()
        elif 'down' in event and event['down']:
            self._data[self.hole_name()] = self._data[self.hole_name()][0:-1]
            self.log(f"Deleted data point for {self.hole_name()}")
            self.vibrate()
        elif 'cross' in event and event['cross']:
            self.desk._listening = False
            self.log("Saving data to file and exiting")
            self.save_data()
            self.vibrate()
            print('Wait for terminal to shut down.....')
            rospy.signal_shutdown("Finished recording data")
            return
        elif 'circle' in event and event['circle']:
            self._active_hole = (self._active_hole + 1) % 2
            self.log(f"Switched to hole {self._active_hole}")
            self.vibrate(duration=1)
        else:
            self.log("Unknown key pressed")
        self.print_status()

    def print_info(self):
        self.log("Press 'check' to add a data point")
        self.log("Press 'down' to delete the last data point")
        self.log("Press 'o' to switch between holes")
        self.log("Press 'x' to save the data and quit.")
