import "."
import QtQuick 2
import QtQuick.Controls 1.4
import QtQuick.Controls.Styles 1.4
import QtQuick.Extras 1.4
import QtQuick.Extras.Private 1.0
import QtGraphicalEffects 1.0

Rectangle {
    width: 1024
    height: 600
    color: "#000000"

    // Define an enumeration for the car states
    enum CarState {
        Drive,
        Reverse,
        Neutral,
        Parked
    }

    /*Left_arrow {
        x: 50
        y: 50
        anchors {
            top: parent.top
        }
    }*/

    CenterScreenWidget {
        anchors {
            horizontalCenter: parent.horizontalCenter
            top: label3.bottom
        }
    }

    To60Widget {
        anchors {
            horizontalCenter: parent.horizontalCenter
            bottom: parent.bottom
            bottomMargin: 100
        }
    }

    SpeedometerGauge {
        scale: 1.3
        anchors {
            top: parent.top
            right: parent.right
            rightMargin: 75
            bottom: parent.bottom
        }
    }

    RPMGauge {
        scale: 1.3
        anchors {
            top: parent.top
            left: parent.left
            leftMargin: 75
            bottom: parent.bottom
        }
    }

    


    //Labels {
    //    id: label1
    //    label: "Intake Pressure"
    //    currValue: intakePressureLabel.currValue
    //    unit: "kPa"
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //    borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.right: label2.left
    //    anchors.rightMargin: 10
    //    anchors.verticalCenter: label2.verticalCenter
    // }

    //Labels {
    //    id: label2
    //    label: "Intake Temp"
    //    currValue: intakeTempLabel.currValue
    //    unit: "°C"
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //    borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.right: label3.left
    //    anchors.rightMargin: 10
    //    anchors.verticalCenter: label3.verticalCenter
    //}

    StringLabels {
        id: label3
        label: "Run Time"
        currValue: runtimeLabel.currValue
        fontSize: 18
        color: "white"
        borderColor: "#FF0000" // Example border color
        borderWidth: 2 // Example border width
        borderRadius: 10 // Example border radius for rounded corners
        anchors.top: parent.top
        anchors.topMargin: 10
        anchors.right: parent.horizontalCenter
    }

    //Labels {
    //    id: label4
    //    label: "Fuel Level"
    //    currValue: fuelLevelLabel.currValue
    //    unit: "%"
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //    borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.left: label3.right
    //    anchors.leftMargin: 10
    //    anchors.verticalCenter: label3.verticalCenter
    //}

    //StringLabels {
    //    id: label5
    //    label: "Fuel Type"
    //    currValue: fuelTypeLabel.currValue
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //    borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.left: label4.right
    //    anchors.leftMargin: 10
    //    anchors.verticalCenter: label4.verticalCenter
    //}

    //Labels {
    //    id: label6
    //    label: "Engine Load"
    //    currValue: engineLoadLabel.currValue
    //    unit: "%"
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //    borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.top: label1.bottom
    //    anchors.topMargin: 5
    //    anchors.horizontalCenter: label1.horizontalCenter
    //}

    //Labels {
    //    id: label7
    //    label: "Throttle Position"
    //    currValue: throttlePosLabel.currValue
    //    unit: "%"
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //    borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.top: label2.bottom
    //    anchors.topMargin: 5
    //    anchors.horizontalCenter: label2.horizontalCenter
    // }

    //Labels {
    //    id: label8
    //    label: "Barometric Pres"
    //    currValue: barometricPressureLabel.currValue
    //    unit: "kPa"
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //   borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.top: label3.bottom
    //    anchors.topMargin: 5
    //    anchors.horizontalCenter: label3.horizontalCenter
    //}

    Image {
        id: celIcon
        source: checkEngine.mil ? "images/cel_on.png" : "images/cel_off.png"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: label3.bottom
        anchors.topMargin: 100
        width: 48
        height: 48
    }

    Text {
        text: checkEngine.dtcCount > 0 ? "(" + checkEngine.dtcCount + ")" : ""
        anchors.top: celIcon.bottom
        anchors.horizontalCenter: celIcon.horizontalCenter
        color: "red"
        font.pixelSize: 18
    }

    //Labels {
    //    id: label9
    //    label: "Throttle Accel"
    //    currValue: throttleAcceleratorLabel.currValue
    //    unit: "%"
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //    borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.top: label4.bottom
    //    anchors.topMargin: 5
    //    anchors.horizontalCenter: label4.horizontalCenter
    //}

    //Labels {
    //    id: label10
    //    label: "Absolute Load"
    //    currValue: absoluteLoadLabel.currValue
    //    unit: "%"
    //    fontSize: 18
    //    color: "white"
    //    borderColor: "#FF0000" // Example border color
    //    borderWidth: 2 // Example border width
    //    borderRadius: 10 // Example border radius for rounded corners
    //    anchors.top: label5.bottom
    //    anchors.topMargin: 5
    //    anchors.horizontalCenter: label5.horizontalCenter
    //}

    Labels {
        id: label11
        label: "Oil Pressure"
        currValue: oilPressureLabel.currValue
        unit: "psi"
        fontSize: 18
        color: "white"
        borderColor: "#FF0000"
        borderWidth: 2
        borderRadius: 10
        anchors.top: parent.top
        anchors.topMargin: 10
        anchors.left: label3.right
    }


    BarMeter {
        id: temperatureBar

        mainValue: temperature.currValue
        maxValue: 200

        label_name: "Temperature(Coolant)"
        unitValue: "°C"

        color: "transparent"    // Only changes the background color with the labels

        anchors.left: parent.left
        anchors.leftMargin: 20
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 20

    }

    BarMeter {
        id: fualBar

        mainValue: fuelLevelLabel.currValue
        maxValue: 100

        label_name: "Fuel"
        unitValue: "%"

        color: "transparent"    // Only changes the background color with the labels

        anchors.right: parent.right
        anchors.rightMargin: 20
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 20

    }

    

    Button {
        id: switchButton
        property string color: "black" // Text color
        Rectangle {
            property string color: "red" // Button background color
            border.color: "white" // Button border color
            border.width: 2 // Button border width
            radius: 10 // Rounded corners
        }
        width: 40 // Adjust the width of the button
        height: 40 // Adjust the height of the button

        MouseArea {
            anchors.fill: parent
                onClicked: {
                console.log("Button clicked")
                // Add any actions you want the button to perform here
                try {
                    ld.source = "Second_row.qml"
                } catch (error) {
                    console.error(error);
                }
                
            }
        }

        Loader{
            id: ld
            anchors.centerIn: dashboardGUI
        }
    }
    

}
